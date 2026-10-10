"""Patient section (Neha)."""
import re
import uuid

from flask import Blueprint, redirect, render_template, request, session, url_for

from services.storage import find_by, load_data, login_required, save_data

patient_bp = Blueprint("patient", __name__, url_prefix="/patient")

SCHEMES = ["Medical card", "DPS", "Private"]
EIRCODE = re.compile(r"^[A-Z0-9]{3}\s?[A-Z0-9]{4}$")


@patient_bp.route("/start")
def start():
    """Choose: set up a new profile, or continue as an existing demo patient."""
    data = load_data()
    return render_template("patient_start.html", patients=data["patients"])


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

        if not errors:
            patient = {"id": "p" + uuid.uuid4().hex[:6], **form, "phone": phone_digits}
            data["patients"].append(patient)
            save_data(data)
            session.clear()
            session["role"] = "patient"
            session["user_id"] = patient["id"]
            return redirect(url_for("patient.home"))

    return render_template("patient_setup.html", form=form, errors=errors, schemes=SCHEMES,
                           doctors=data["doctors"], pharmacies=data["pharmacies"])


@patient_bp.route("/home")
@login_required("patient")
def home():
    data = load_data()
    patient = find_by(data["patients"], "id", session["user_id"])
    if not patient:  # profile was deleted from data.json
        session.clear()
        return redirect(url_for("welcome"))
    pharmacy = find_by(data["pharmacies"], "id", patient["pharmacy_id"])
    return render_template("patient_home.html", patient=patient, pharmacy=pharmacy)