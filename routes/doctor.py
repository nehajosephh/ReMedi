import calendar
import json
from datetime import date, datetime
from pathlib import Path

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

doctor_bp = Blueprint("doctor", __name__, url_prefix="/gp")

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "data.json"
RENEWAL_MONTHS = {"6": 6, "3": 3, "1": 1}
REVIEW_OVERDUE_DAYS = 365


def load_data():
    with open(DATA_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def find(items, key, value):
    return next((item for item in items if item.get(key) == value), None)


def add_months(start, months):
    month_index = start.month - 1 + months
    year = start.year + month_index // 12
    month = month_index % 12 + 1
    day = min(start.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def current_gp(data):
    reg = session.get("gp_reg")
    if session.get("role") != "doctor" or not reg:
        return None
    return find(data.get("gps", []), "reg_number", reg)


def check_login(data, reg, practice_id, password):
    if not reg or not practice_id or not password:
        return "Fill in your registration number, practice and password."
    if not reg.isdigit():
        return "Medical Council registration numbers only contain digits."
    doctor = find(data.get("gps", []), "reg_number", reg)
    if doctor is None:
        return "We couldn't find that registration number on the register."
    if doctor.get("practice_id") != practice_id:
        return "That registration number isn't linked to the practice you chose."
    if doctor.get("password") != password:
        return "That password is wrong."
    return None


def review_overdue(patient):
    last_review = patient.get("last_review")
    if not last_review:
        return True
    days = (date.today() - date.fromisoformat(last_review)).days
    return days > REVIEW_OVERDUE_DAYS


def build_view(renewal, patient):
    view = dict(renewal)
    view["patient"] = patient
    view["review_overdue"] = review_overdue(patient)
    view["requested_time"] = datetime.fromisoformat(renewal["requested_at"]).strftime("%H:%M")
    return view


def update_medication(patient, medication_name, months):
    for medication in patient.get("medications", []):
        if medication.get("name") == medication_name:
            medication["expiry_date"] = add_months(date.today(), months).isoformat()
            medication["repeats_total"] = months
            medication["repeats_left"] = months


@doctor_bp.route("/login", methods=["GET", "POST"])
def login():
    data = load_data()
    practices = data.get("practices", [])
    if request.method == "GET":
        return render_template("doctor_login.html", practices=practices, form={}, error=None)

    reg = request.form.get("reg_number", "").strip()
    practice_id = request.form.get("practice_id", "")
    password = request.form.get("password", "")
    error = check_login(data, reg, practice_id, password)
    if error:
        return render_template("doctor_login.html", practices=practices, form=request.form, error=error), 400

    session.clear()
    session["role"] = "doctor"
    session["gp_reg"] = reg
    return redirect(url_for("doctor.home"))


@doctor_bp.route("/")
def home():
    data = load_data()
    doctor = current_gp(data)
    if doctor is None:
        return redirect(url_for("doctor.login"))

    patients = {
        patient["id"]: patient
        for patient in data.get("patients", [])
        if patient.get("practice_id") == doctor["practice_id"]
    }
    renewals = [
        build_view(renewal, patients[renewal["patient_id"]])
        for renewal in data.get("renewal_requests", [])
        if renewal.get("patient_id") in patients
    ]
    pending = sorted(
        (renewal for renewal in renewals if renewal["status"] == "pending"),
        key=lambda renewal: renewal["requested_at"],
    )
    selected = find(pending, "id", request.args.get("request")) or (pending[0] if pending else None)

    today = date.today().isoformat()
    stats = {
        "pending": len(pending),
        "overdue": sum(1 for renewal in pending if renewal["review_overdue"]),
        "renewed_today": sum(
            1
            for renewal in renewals
            if renewal["status"] == "renewed" and renewal.get("decided_at", "").startswith(today)
        ),
    }
    practice = find(data.get("practices", []), "id", doctor["practice_id"])
    return render_template(
        "doctor_dashboard.html",
        doctor=doctor,
        practice=practice,
        pending=pending,
        selected=selected,
        stats=stats,
    )


@doctor_bp.route("/requests/<request_id>", methods=["POST"])
def decide(request_id):
    data = load_data()
    doctor = current_gp(data)
    if doctor is None:
        return redirect(url_for("doctor.login"))

    renewal = find(data.get("renewal_requests", []), "id", request_id)
    patient = find(data.get("patients", []), "id", renewal["patient_id"]) if renewal else None
    if renewal is None or patient is None or patient.get("practice_id") != doctor["practice_id"]:
        flash("That request doesn't exist or isn't for your practice.", "error")
        return redirect(url_for("doctor.home"))
    if renewal["status"] != "pending":
        flash("That request has already been dealt with.", "error")
        return redirect(url_for("doctor.home"))

    action = request.form.get("action")
    if action == "renew":
        months = RENEWAL_MONTHS.get(request.form.get("months", ""))
        if months is None:
            flash("Choose how long to renew the prescription for.", "error")
            return redirect(url_for("doctor.home", request=request_id))
        renewal["status"] = "renewed"
        renewal["renewed_months"] = months
        update_medication(patient, renewal["medication"], months)
        message = f"Renewed {renewal['medication']} for {patient['name']}. The pharmacy can now fill it."
    elif action == "review":
        renewal["status"] = "review_requested"
        message = f"Asked {patient['name']} to book a medication review."
    elif action == "decline":
        reason = request.form.get("reason", "").strip()
        if not reason:
            flash("Add a reason so the pharmacy can explain it to the patient.", "error")
            return redirect(url_for("doctor.home", request=request_id))
        renewal["status"] = "declined"
        renewal["decline_reason"] = reason
        message = f"Declined {renewal['medication']} for {patient['name']}."
    else:
        flash("Something went wrong. Please try again.", "error")
        return redirect(url_for("doctor.home", request=request_id))

    renewal["decided_at"] = datetime.now().isoformat(timespec="minutes")
    renewal["decided_by"] = doctor["reg_number"]
    save_data(data)
    flash(message, "success")
    return redirect(url_for("doctor.home"))