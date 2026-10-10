"""Patient section (Neha)."""
import re
import uuid
from datetime import datetime

from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for
from services.prescription_rules import item_state, next_due_date, parse_date, repeats_left, today

from services.ai_assistant import understand_request
from services.storage import find_by, load_data, login_required, save_data

patient_bp = Blueprint("patient", __name__, url_prefix="/patient")

SCHEMES = ["Medical card", "DPS", "Private"]
REMINDER_DAYS = 3          # remind patients this many days before their order is due
DELIVERY_FEE_CENTS = 300   # EUR 3, must match routes/payments.py
EIRCODE = re.compile(r"^[A-Z0-9]{3}\s?[A-Z0-9]{4}$")


@patient_bp.route("/start")
def start():
    """Choose: set up a new profile, or continue as an existing demo patient."""
    data = load_data()
    return render_template("patient/start.html", patients=data["patients"])


@patient_bp.route("/continue/<patient_id>")
def continue_as(patient_id):
    data = load_data()
    if not find_by(data["patients"], "id", patient_id):
        return redirect(url_for("patient.start"))
    session.clear()
    session["role"] = "patient"
    session["user_id"] = patient_id
    return redirect(url_for("patient.home"))


@patient_bp.route("/setup", methods=["GET", "POST"])
def setup():
    data = load_data()
    form, errors = {}, {}

    if request.method == "POST":
        form = {k: request.form.get(k, "").strip() for k in
                ["first_name", "last_name", "dob", "phone", "address", "eircode",
                 "scheme", "doctor_id", "pharmacy_id", "delivery"]}
        form["eircode"] = form["eircode"].upper()
        phone_digits = re.sub(r"\D", "", form["phone"])

        if not form["first_name"]:
            errors["first_name"] = "Enter your first name."
        if not form["last_name"]:
            errors["last_name"] = "Enter your last name."
        if not form["dob"]:
            errors["dob"] = "Enter your date of birth."
        if len(phone_digits) < 9:
            errors["phone"] = "Enter a valid phone number, like 085 123 4567."
        if not form["address"]:
            errors["address"] = "Enter your address so we can deliver."
        if form["eircode"] and not EIRCODE.match(form["eircode"]):
            errors["eircode"] = "That doesn't look like an Eircode (e.g. D09 X2Y3)."
        if form["scheme"] not in SCHEMES:
            errors["scheme"] = "Choose how you pay for prescriptions."
        if not find_by(data["doctors"], "id", form["doctor_id"]):
            errors["doctor_id"] = "Choose your GP."
        if not find_by(data["pharmacies"], "id", form["pharmacy_id"]):
            errors["pharmacy_id"] = "Choose your pharmacy."
        if form["delivery"] not in ("home", "collect"):
            form["delivery"] = "home"

        # Same name, date of birth and phone = same person. Log them in instead of making a duplicate.
        existing = next((p for p in data["patients"]
            if p["first_name"].lower() == form["first_name"].lower()
            and p["last_name"].lower() == form["last_name"].lower()
            and p["dob"] == form["dob"] and p["phone"] == phone_digits), None)
        if not errors and existing:
            session.clear()
            session["role"] = "patient"
            session["user_id"] = existing["id"]
            return redirect(url_for("patient.home"))

        if not errors:
            patient = {"id": "p" + uuid.uuid4().hex[:6], **form, "phone": phone_digits}
            data["patients"].append(patient)
            save_data(data)
            session.clear()
            session["role"] = "patient"
            session["user_id"] = patient["id"]
            return redirect(url_for("patient.home"))

    return render_template("patient/setup.html", form=form, errors=errors, schemes=SCHEMES,
                           doctors=data["doctors"], pharmacies=data["pharmacies"])


def current_patient(data):
    """The logged-in patient, or None."""
    return find_by(data["patients"], "id", session.get("user_id"))


def last_order_items(data, patient_id):
    """Prescription ids from this patient's most recent order (what they had last month).
    If the GP has renewed a script since, follow it to the new prescription id."""
    orders = [o for o in data["orders"] if o["patient_id"] == patient_id and o.get("status") != "cancelled"]
    if not orders:
        return []
    latest = max(orders, key=lambda o: o["created_at"])
    renewed = {rx["replaces"]: rx["id"] for rx in data["prescriptions"] if rx.get("replaces")}
    ids = []
    for item in latest["items"]:
        rx_id = item.get("prescription_id")
        while rx_id in renewed:
            rx_id = renewed[rx_id]
        if rx_id:
            ids.append(rx_id)
    return ids


def build_med_list(data, patient_id):
    """Each of the patient's prescriptions plus everything the screen needs to show it."""
    last_items = last_order_items(data, patient_id)
    meds = []
    for rx in data["prescriptions"]:
        if rx["patient_id"] != patient_id or rx.get("status") == "replaced":
            continue
        can_order, state, message = item_state(rx)
        last = rx.get("last_dispensed")
        meds.append({
            **rx,
            "can_order": can_order,
            "state": state,
            "message": message,
            "repeats_left": repeats_left(rx),
            "in_last_order": rx["id"] in last_items,
            # ticked by default if they had it last month and it can still be ordered
            "ticked": can_order and rx["id"] in last_items,
            "last_ordered": parse_date(last).strftime("%B") if last else None,
        })
    return meds


@patient_bp.route("/home")
@login_required("patient")
def home():
    data = load_data()
    patient = current_patient(data)
    if not patient:  # profile was deleted from data.json
        session.clear()
        return redirect(url_for("welcome"))
    meds = build_med_list(data, patient["id"])
    # base the due date on what they normally order each month
    due = next_due_date([m for m in meds if m["ticked"]])
    due_text = "Any time"
    if due:
        due_text = "Due now" if due <= today() else due.strftime("%a %d %b").replace(" 0", " ")

    # Reminder 3 days before the monthly order is due (a real version would also text or email)
    current = active_order(data, patient["id"])
    days_left = (due - today()).days if due else None
    remind = current is None and days_left is not None and days_left <= REMINDER_DAYS
    return render_template("patient/home.html", patient=patient, meds=meds, due=due_text,
                           error=request.args.get("error"), current_order=current,
                           remind=remind, days_left=days_left)


@patient_bp.route("/review", methods=["POST"])
@login_required("patient")
def review():
    """Check what the patient ticked. Never trust the browser: re-check every item here."""
    data = load_data()
    patient = current_patient(data)
    meds = {m["id"]: m for m in build_med_list(data, patient["id"])}

    chosen = [i for i in request.form.getlist("items") if i in meds and meds[i]["can_order"]]
    gp_requests = [i for i in request.form.getlist("gp_requests") if i in meds and not meds[i]["can_order"]]
    delivery = "collect" if request.form.get("delivery") == "collect" else "home"

    if not chosen:
        return redirect(url_for("patient.home", error="Tick at least one medication to continue."))

    # Remember the choice for the next screen. The AI may have drafted a note for the pharmacist.
    session["draft_order"] = {"items": chosen, "gp_requests": gp_requests, "delivery": delivery,
                              "ai_message": request.form.get("ai_message", "")[:300]}
    return render_template("patient/review.html", patient=patient,
                           items=[meds[i] for i in chosen],
                           gp_items=[meds[i] for i in gp_requests],
                           delivery=delivery,
                           note=request.form.get("pharmacist_note", "")[:500])


def active_order(data, patient_id):
    """An order that's still being dealt with, so we don't let the patient send two at once."""
    finished = {"delivered", "collected", "cancelled"}
    return next((o for o in data["orders"]
                 if o["patient_id"] == patient_id and o.get("status") not in finished), None)


@patient_bp.route("/place-order", methods=["POST"])
@login_required("patient")
def place_order():
    """Save the order in the shared format so it appears on the pharmacy dashboard,
    and send any 'Ask my GP' items to the GP as renewal requests."""
    data = load_data()
    patient = current_patient(data)
    draft = session.get("draft_order")
    if not draft:
        return redirect(url_for("patient.home", error="Your order timed out. Please tick your items again."))
    if active_order(data, patient["id"]):
        return redirect(url_for("patient.home", error="You already have an order with the pharmacy. "
                                                      "Message them if you need to change it."))

    meds = {m["id"]: m for m in build_med_list(data, patient["id"])}
    items = [meds[i] for i in draft["items"] if i in meds and meds[i]["can_order"]]  # check again
    if not items:
        return redirect(url_for("patient.home", error="None of those items can be ordered any more."))
    gp_items = [meds[i] for i in draft["gp_requests"] if i in meds and not meds[i]["can_order"]]
    note = request.form.get("note", "").strip()[:500]
    now = datetime.now().isoformat(timespec="minutes")
    delivery = draft["delivery"] == "home"

    order = {
        "id": "ord" + uuid.uuid4().hex[:6],
        "patient_id": patient["id"],
        "pharmacy_id": patient["pharmacy_id"],
        "created_at": now,
        # anything waiting on the GP needs the pharmacist's attention
        "status": "needs_attention" if gp_items else "pending",
        # price isn't known until the pharmacist checks it, then they send an invoice
        "payment_method": "card" if delivery else "in_store",
        "payment_status": "not_invoiced",
        "delivery_fee_cents": DELIVERY_FEE_CENTS if delivery else 0,
        "fulfilment": "delivery" if delivery else "collection",
        "delivery_date": "",
        "delivery_slot": "",
        "patient_message": note,
        "ai_message": draft.get("ai_message", ""),
        "items": [{"prescription_id": m["id"], "medicine_name": f"{m['drug']} {m['strength']}",
                   "quantity": m["qty"]} for m in items],
        "gp_requests": [m["id"] for m in gp_items],
    }
    data["orders"].append(order)

    # "Ask my GP" items become renewal requests on the GP dashboard (no duplicates)
    for m in gp_items:
        already = any(r.get("prescription_id") == m["id"] and r.get("status") == "pending"
                      for r in data.setdefault("renewal_requests", []))
        if already:
            continue
        data["renewal_requests"].append({
            "id": "r" + uuid.uuid4().hex[:6],
            "patient_id": patient["id"],
            "pharmacy_id": patient["pharmacy_id"],
            "prescription_id": m["id"],
            "medication": f"{m['drug']} {m['strength']}",
            "dosage": f"{m['directions']}, {m['qty']} tablets",
            "reason": m["message"].split(" on ")[0].lower() if m["message"] else m["state"],
            "requested_at": now,
            "previous_script": f"Previous script issued {m.get('issued', 'unknown')}, "
                               f"{m['repeats_total']} dispensings.",
            "note": f"Patient asked for this in their monthly order on ReMedi. {note}".strip(),
            "status": "pending",
        })

    save_data(data)
    session.pop("draft_order", None)
    return redirect(url_for("patient.order_status", order_id=order["id"]))


@patient_bp.route("/order/<order_id>")
@login_required("patient")
def order_status(order_id):
    data = load_data()
    patient = current_patient(data)
    order = find_by(data["orders"], "id", order_id)
    if not order or order["patient_id"] != patient["id"]:
        return redirect(url_for("patient.home"))
    pharmacy = find_by(data["pharmacies"], "id", order["pharmacy_id"])
    gp_names = [f"{rx['drug']} {rx['strength']}" for rx in data["prescriptions"]
                if rx["id"] in order.get("gp_requests", [])]
    return render_template("patient/order.html", patient=patient, order=order,
                           pharmacy=pharmacy, gp_names=gp_names,
                           error=request.args.get("error"),
                           just_paid=request.args.get("paid") == "1",
                           cancelled=request.args.get("cancelled") == "1")


@patient_bp.route("/assist", methods=["POST"])
@login_required("patient")
def assist():
    """AI search bar: turn 'I don't need the cholesterol meds' into ticks and unticks."""
    data = load_data()
    patient = current_patient(data)
    body = request.get_json(silent=True) or {}
    meds = build_med_list(data, patient["id"])
    ticked = [i for i in body.get("ticked", []) if any(m["id"] == i for m in meds)]
    result = understand_request(body.get("message", ""), meds, ticked,
                                last_order_items(data, patient["id"]))
    if not result["ok"]:
        return jsonify(result), 400
    return jsonify(result)
