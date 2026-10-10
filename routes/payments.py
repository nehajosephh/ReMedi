"""Payments: the pharmacy prices an order and sends an invoice, the patient pays it with Stripe.

Why invoices: what a patient owes depends on their scheme (medical card, DPS, private) and on
what the pharmacist actually dispenses, so the price is only known once the order is checked.

Flow:
  1. Pharmacist checks the order, enters the medicine charge -> POST /payments/invoice/<order_id>
  2. Patient sees "Ready, you owe EUR X" on their order page
     - Delivery: pays online -> POST /payments/checkout/<order_id> -> Stripe Checkout (sandbox)
     - Collection: pays in store, pharmacist marks it paid
  3. Stripe sends the patient back -> GET /payments/success. We ask Stripe directly whether the
     session was paid before marking the order as paid. We never trust the URL alone.
"""
import os
from datetime import datetime

from flask import Blueprint, jsonify, redirect, request, session, url_for

from services.storage import find_by, load_data, save_data

try:
    import stripe
except ImportError:
    stripe = None

payments_bp = Blueprint("payments", __name__, url_prefix="/payments")

DELIVERY_FEE_CENTS = 300   # EUR 3 home delivery, added to the invoice
CURRENCY = "eur"


def now():
    return datetime.now().isoformat(timespec="minutes")


def stripe_client():
    """Return the stripe module set up with our TEST key, or explain what's wrong."""
    key = os.getenv("STRIPE_SECRET_KEY", "")
    if stripe is None:
        return None, "Stripe isn't installed. Run: pip install stripe"
    if not key:
        return None, "Card payments aren't set up yet (no STRIPE_SECRET_KEY in .env)."
    if not key.startswith("sk_test_"):
        return None, "Use a Stripe TEST key (sk_test_...). Real payments aren't allowed."
    stripe.api_key = key
    return stripe, None


def as_dict(obj):
    """Newer versions of the Stripe library return objects, not dicts."""
    return obj.to_dict() if hasattr(obj, "to_dict") else dict(obj)


# ---------------- 1. pharmacy sends the invoice ----------------

@payments_bp.route("/invoice/<order_id>", methods=["POST"])
def send_invoice(order_id):
    if session.get("role") != "pharmacy_demo":
        return jsonify({"ok": False, "error": "Only pharmacy staff can send invoices."}), 403
    body = request.get_json(silent=True) or request.form
    try:
        medicines_cents = round(float(body.get("medicines_euro", "")) * 100)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "Enter the medicine charge in euro, e.g. 4.50"}), 400
    if medicines_cents < 0 or medicines_cents > 100000:
        return jsonify({"ok": False, "error": "That amount doesn't look right."}), 400

    data = load_data()
    order = find_by(data["orders"], "id", order_id)
    if not order or order.get("pharmacy_id") != session.get("pharmacy_id"):
        return jsonify({"ok": False, "error": "That order isn't at your pharmacy."}), 404
    if order.get("payment_status") == "paid":
        return jsonify({"ok": False, "error": "This order has already been paid."}), 400

    delivery_cents = DELIVERY_FEE_CENTS if order.get("fulfilment") == "delivery" else 0
    total = medicines_cents + delivery_cents
    order["invoice"] = {"medicines_cents": medicines_cents, "delivery_cents": delivery_cents,
                        "total_cents": total, "sent_at": now()}
    order["status"] = "ready"
    if total == 0:
        order["payment_status"] = "paid"            # nothing to pay
    elif order.get("fulfilment") == "delivery":
        order["payment_status"] = "awaiting_payment"  # patient pays online before it goes out
    else:
        order["payment_status"] = "pay_in_store"
    order.setdefault("messages", []).append(
        {"from": "pharmacy", "time": now(),
         "text": f"Your order is ready. Total EUR {total / 100:.2f}."})
    save_data(data)
    return jsonify({"ok": True, "order": order})


@payments_bp.route("/mark-paid/<order_id>", methods=["POST"])
def mark_paid_in_store(order_id):
    """Pharmacist takes payment at the counter for a collection order."""
    if session.get("role") != "pharmacy_demo":
        return jsonify({"ok": False, "error": "Only pharmacy staff can do this."}), 403
    data = load_data()
    order = find_by(data["orders"], "id", order_id)
    if not order or order.get("pharmacy_id") != session.get("pharmacy_id"):
        return jsonify({"ok": False, "error": "That order isn't at your pharmacy."}), 404
    order["payment_status"] = "paid"
    order["paid_at"] = now()
    order["paid_by"] = "in store"
    order["status"] = "collected"
    save_data(data)
    return jsonify({"ok": True, "order": order})


@payments_bp.route("/mark-delivered/<order_id>", methods=["POST"])
def mark_delivered(order_id):
    """Driver has dropped off a paid delivery order."""
    if session.get("role") != "pharmacy_demo":
        return jsonify({"ok": False, "error": "Only pharmacy staff can do this."}), 403
    data = load_data()
    order = find_by(data["orders"], "id", order_id)
    if not order or order.get("pharmacy_id") != session.get("pharmacy_id"):
        return jsonify({"ok": False, "error": "That order isn't at your pharmacy."}), 404
    if order.get("payment_status") != "paid":
        return jsonify({"ok": False, "error": "Wait for the patient to pay before it goes out."}), 400
    order["status"] = "delivered"
    order["delivered_at"] = now()
    save_data(data)
    return jsonify({"ok": True, "order": order})


# ---------------- 2. patient pays with Stripe Checkout ----------------

@payments_bp.route("/checkout/<order_id>", methods=["POST"])
def checkout(order_id):
    if session.get("role") != "patient":
        return redirect(url_for("welcome"))
    data = load_data()
    order = find_by(data["orders"], "id", order_id)
    back = url_for("patient.order_status", order_id=order_id)
    if not order or order["patient_id"] != session.get("user_id"):
        return redirect(url_for("patient.home"))
    if order.get("payment_status") != "awaiting_payment" or not order.get("invoice"):
        return redirect(back)

    client, problem = stripe_client()
    if problem:
        return redirect(back + "?error=" + problem)

    invoice = order["invoice"]
    line_items = []
    if invoice["medicines_cents"] > 0:
        names = ", ".join(i["medicine_name"] for i in order["items"])
        line_items.append({"price_data": {"currency": CURRENCY, "unit_amount": invoice["medicines_cents"],
                                          "product_data": {"name": "Prescription medicines",
                                                           "description": names[:250]}},
                           "quantity": 1})
    if invoice["delivery_cents"] > 0:
        line_items.append({"price_data": {"currency": CURRENCY, "unit_amount": invoice["delivery_cents"],
                                          "product_data": {"name": "ReMedi home delivery"}},
                           "quantity": 1})
    try:
        checkout_session = client.checkout.Session.create(
            mode="payment",
            line_items=line_items,
            client_reference_id=order_id,
            metadata={"order_id": order_id, "patient_id": order["patient_id"]},
            success_url=request.host_url.rstrip("/") + url_for("payments.success")
                        + "?order_id=" + order_id + "&session_id={CHECKOUT_SESSION_ID}",
            cancel_url=request.host_url.rstrip("/") + back + "?cancelled=1",
        )
    except Exception as e:
        return redirect(back + "?error=Stripe error: " + str(getattr(e, "user_message", None) or e)[:150])

    order["stripe_session_id"] = checkout_session["id"]
    save_data(data)
    return redirect(checkout_session["url"], code=303)


# ---------------- 3. Stripe sends them back: confirm with Stripe ----------------

@payments_bp.route("/success")
def success():
    order_id = request.args.get("order_id", "")
    back = url_for("patient.order_status", order_id=order_id)
    client, problem = stripe_client()
    if problem:
        return redirect(back + "?error=" + problem)
    try:
        checkout_session = as_dict(client.checkout.Session.retrieve(request.args.get("session_id", "")))
    except Exception:
        return redirect(back + "?error=We couldn't find that payment with Stripe.")

    data = load_data()
    order = find_by(data["orders"], "id", order_id)
    if not order:
        return redirect(url_for("patient.home"))
    if (checkout_session.get("metadata") or {}).get("order_id") != order_id:
        return redirect(back + "?error=That payment belongs to a different order.")
    if checkout_session.get("payment_status") != "paid":
        return redirect(back + "?error=Payment not completed yet.")

    if order.get("payment_status") != "paid":
        order["payment_status"] = "paid"
        order["paid_at"] = now()
        order["paid_by"] = "card (Stripe)"
        order["amount_paid_cents"] = checkout_session.get("amount_total")
        order["stripe_payment_intent"] = checkout_session.get("payment_intent")
        order.setdefault("messages", []).append(
            {"from": "pharmacy", "time": now(), "text": "Payment received. Your order will be delivered soon."})
        save_data(data)
    return redirect(back + "?paid=1")
