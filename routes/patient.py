"""Patient section (Neha)."""
import re
import uuid

from flask import Blueprint, redirect, render_template, request, session, url_for
from services.prescription_rules import item_state, next_due_date, parse_date, repeats_left, today

from services.storage import find_by, load_data, login_required, save_data

patient_bp = Blueprint("patient", __name__, url_prefix="/patient")

SCHEMES = ["Medical card", "DPS", "Private"]
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
    """Prescription ids from this patient's most recent order (what they had last month)."""
    orders = [o for o in data["orders"] if o["patient_id"] == patient_id and o.get("status") != "cancelled"]
    if not orders:
        return []
    latest = max(orders, key=lambda o: o["created"])
    return latest["items"]


def build_med_list(data, patient_id):
    """Each of the patient's prescriptions plus everything the screen needs to show it."""
    last_items = last_order_items(data, patient_id)
    meds = []
    for rx in data["prescriptions"]:
        if rx["patient_id"] != patient_id or rx.get("superseded"):
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
    return render_template("patient/home.html", patient=patient, meds=meds, due=due_text,
                           error=request.args.get("error"))


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

    # Remember the choice for the next screens (review, payment)
    session["draft_order"] = {"items": chosen, "gp_requests": gp_requests, "delivery": delivery}
    return render_template("patient/review.html", patient=patient,
                           items=[meds[i] for i in chosen],
                           gp_items=[meds[i] for i in gp_requests],
                           delivery=delivery)