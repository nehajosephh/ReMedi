import calendar
import json
import unicodedata
import uuid
from datetime import date, datetime
from pathlib import Path

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

doctor_bp = Blueprint("doctor", __name__, url_prefix="/doctor")
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


def full_name(patient):
    return f"{patient.get('first_name', '')} {patient.get('last_name', '')}".strip()


def practice_names(data):
    return sorted({doc["practice"] for doc in data.get("doctors", []) if doc.get("practice")})


def current_doctor(data):
    doctor_id = session.get("doctor_id")
    if session.get("role") != "doctor" or not doctor_id:
        return None
    return find(data.get("doctors", []), "id", doctor_id)


def check_login(data, imc_number, practice, password):
    if not imc_number or not practice or not password:
        return None, "Fill in your registration number, practice and password."
    if not imc_number.isdigit():
        return None, "Medical Council registration numbers only contain digits."
    doc = find(data.get("doctors", []), "imc_number", imc_number)
    if doc is None:
        return None, "We couldn't find that registration number on the register."
    if doc.get("practice") != practice:
        return None, "That registration number isn't linked to the practice you chose."
    if doc.get("password") != password:
        return None, "That password is wrong."
    return doc, None


def review_overdue(patient):
    last_review = patient.get("last_review")
    if not last_review:
        return False
    return (date.today() - date.fromisoformat(last_review)).days > REVIEW_OVERDUE_DAYS


def months_since(iso_date):
    then = date.fromisoformat(iso_date)
    today = date.today()
    months = (today.year - then.year) * 12 + today.month - then.month
    if today.day < then.day:
        months -= 1
    return months


def long_date(iso_date):
    if not iso_date:
        return None
    d = date.fromisoformat(iso_date)
    return f"{d.day} {d.strftime('%B %Y')}"


def month_year(iso_date):
    if not iso_date:
        return None
    return date.fromisoformat(iso_date).strftime("%B %Y")


def build_view(renewal, patient, pharmacies):
    view = dict(renewal)
    view["patient"] = patient
    view["patient_name"] = full_name(patient)
    view["dob_display"] = long_date(patient.get("dob")) or "date unknown"
    view["last_review_display"] = month_year(patient.get("last_review")) or "none recorded"
    view["review_overdue"] = review_overdue(patient)
    view["months_since_review"] = months_since(patient["last_review"]) if patient.get("last_review") else None
    view["requested_time"] = datetime.fromisoformat(renewal["requested_at"]).strftime("%H:%M")
    pharmacy = find(pharmacies, "id", renewal.get("pharmacy_id"))
    view["pharmacy_name"] = pharmacy["name"] if pharmacy else "Unknown pharmacy"
    return view


def issue_prescription(data, renewal, doc, months):
    """Replace the old script with a new one in the shared prescription format."""
    prescriptions = data.setdefault("prescriptions", [])
    old = find(prescriptions, "id", renewal.get("prescription_id"))
    if old is None:  # fall back to matching on the medicine name, e.g. "Amlodipine 5mg"
        old = next((rx for rx in prescriptions
                    if rx.get("patient_id") == renewal["patient_id"]
                    and f"{rx.get('drug')} {rx.get('strength')}" == renewal["medication"]
                    and rx.get("status") != "replaced"), None)
    if old:
        old["status"] = "replaced"
    old = old or {}
    today = date.today()
    prescriptions.append({
        "id": f"rx{uuid.uuid4().hex[:6]}",
        "patient_id": renewal["patient_id"],
        "doctor_id": doc["id"],
        "drug": old.get("drug", renewal["medication"]),
        "strength": old.get("strength", ""),
        "directions": old.get("directions", renewal.get("dosage", "")),
        "qty": old.get("qty", 28),
        "supply_days": old.get("supply_days", 28),
        "repeats_total": months,
        "repeats_used": 0,
        "issued": today.isoformat(),
        "expiry": add_months(today, months).isoformat(),
        "controlled": old.get("controlled", False),
        "important": old.get("important", True),
        "last_dispensed": old.get("last_dispensed"),
        "status": "active",
        "replaces": old.get("id"),
    })


@doctor_bp.route("/login", methods=["GET", "POST"])
def login():
    data = load_data()
    practices = practice_names(data)
    if request.method == "GET":
        return render_template("doctor/doctor_login.html", practices=practices, form={}, error=None)

    imc_number = request.form.get("imc_number", "").strip()
    practice = request.form.get("practice", "")
    password = request.form.get("password", "")
    doc, error = check_login(data, imc_number, practice, password)
    if error:
        return render_template("doctor/doctor_login.html", practices=practices, form=request.form, error=error), 400

    session.clear()
    session["role"] = "doctor"
    session["doctor_id"] = doc["id"]
    return redirect(url_for("doctor.home"))


@doctor_bp.route("/")
def home():
    data = load_data()
    doc = current_doctor(data)
    if doc is None:
        return redirect(url_for("doctor.login"))

    patients = {p["id"]: p for p in data.get("patients", []) if p.get("doctor_id") == doc["id"]}
    pharmacies = data.get("pharmacies", [])
    renewals = [
        build_view(renewal, patients[renewal["patient_id"]], pharmacies)
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
    return render_template(
        "doctor/doctor_dashboard.html",
        doctor=doc,
        pending=pending,
        selected=selected,
        stats=stats,
    )


@doctor_bp.route("/requests/<request_id>", methods=["POST"])
def decide(request_id):
    data = load_data()
    doc = current_doctor(data)
    if doc is None:
        return redirect(url_for("doctor.login"))

    renewal = find(data.get("renewal_requests", []), "id", request_id)
    patient = find(data.get("patients", []), "id", renewal["patient_id"]) if renewal else None
    if renewal is None or patient is None or patient.get("doctor_id") != doc["id"]:
        flash("That request doesn't exist or isn't for one of your patients.", "error")
        return redirect(url_for("doctor.home"))
    if renewal["status"] != "pending":
        flash("That request has already been dealt with.", "error")
        return redirect(url_for("doctor.home"))

    name = full_name(patient)
    action = request.form.get("action")
    if action == "renew":
        months = RENEWAL_MONTHS.get(request.form.get("months", ""))
        if months is None:
            flash("Choose how long to renew the prescription for.", "error")
            return redirect(url_for("doctor.home", request=request_id))
        renewal["status"] = "renewed"
        renewal["renewed_months"] = months
        issue_prescription(data, renewal, doc, months)
        message = f"Renewed {renewal['medication']} for {name}. The pharmacy can now fill it."
    elif action == "review":
        renewal["status"] = "review_requested"
        message = f"Asked {name} to book a medication review."
    elif action == "decline":
        reason = request.form.get("reason", "").strip()
        if not reason:
            flash("Add a reason so the pharmacy can explain it to the patient.", "error")
            return redirect(url_for("doctor.home", request=request_id))
        renewal["status"] = "declined"
        renewal["decline_reason"] = reason
        message = f"Declined {renewal['medication']} for {name}."
    else:
        flash("Something went wrong. Please try again.", "error")
        return redirect(url_for("doctor.home", request=request_id))

    renewal["decided_at"] = datetime.now().isoformat(timespec="minutes")
    renewal["decided_by"] = doc["id"]
    save_data(data)
    flash(message, "success")
    return redirect(url_for("doctor.home"))
EXPIRING_SOON_DAYS = 30
STATE_ORDER = {"expired": 0, "soon": 1, "active": 2}


def prescription_state(prescription):
    today = date.today()
    expiry = prescription.get("expiry_date")
    if expiry and date.fromisoformat(expiry) < today:
        return "expired", "Expired"
    if prescription.get("repeats_left", 1) <= 0:
        return "expired", "No repeats left"
    if expiry and (date.fromisoformat(expiry) - today).days <= EXPIRING_SOON_DAYS:
        return "soon", "Expires soon"
    return "active", "Active"


def prescription_view(prescription):
    view = dict(prescription)
    view["state"], view["state_label"] = prescription_state(prescription)
    view["expiry_display"] = long_date(prescription.get("expiry_date")) or "no expiry date"
    view["issued_display"] = long_date(prescription.get("issued_at")) or "unknown"
    return view


def current_prescriptions(data, patient_id):
    scripts = [
        prescription_view(p)
        for p in data.get("prescriptions", [])
        if p.get("patient_id") == patient_id and p.get("status") != "replaced"
    ]
    return sorted(scripts, key=lambda s: (STATE_ORDER[s["state"]], s.get("medication", "")))


def plain(text):
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).lower()


def my_patient(data, doc, patient_id):
    patient = find(data.get("patients", []), "id", patient_id)
    if patient is None or patient.get("doctor_id") != doc["id"]:
        return None
    return patient


@doctor_bp.route("/patients")
def patients():
    data = load_data()
    doc = current_doctor(data)
    if doc is None:
        return redirect(url_for("doctor.login"))

    query = request.args.get("q", "").strip()
    rows = []
    for patient in data.get("patients", []):
        if patient.get("doctor_id") != doc["id"]:
            continue
        name = full_name(patient)
        if query and plain(query) not in plain(name):
            continue
        scripts = current_prescriptions(data, patient["id"])
        rows.append({
            "id": patient["id"],
            "name": name,
            "dob_display": long_date(patient.get("dob")) or "date unknown",
            "script_count": len(scripts),
            "needs_attention": sum(1 for s in scripts if s["state"] != "active"),
            "review_overdue": review_overdue(patient),
        })
    rows.sort(key=lambda row: row["name"])
    return render_template("doctor/doctor_patients.html", doctor=doc, patients=rows, query=query, active="patients")


@doctor_bp.route("/patients/<patient_id>")
def patient_profile(patient_id):
    data = load_data()
    doc = current_doctor(data)
    if doc is None:
        return redirect(url_for("doctor.login"))

    patient = my_patient(data, doc, patient_id)
    if patient is None:
        flash("That patient isn't registered with you.", "error")
        return redirect(url_for("doctor.patients"))

    pharmacy = find(data.get("pharmacies", []), "id", patient.get("pharmacy_id"))
    pending = [
        r for r in data.get("renewal_requests", [])
        if r.get("patient_id") == patient_id and r.get("status") == "pending"
    ]
    return render_template(
        "doctor/doctor_patient.html",
        doctor=doc,
        patient=patient,
        patient_name=full_name(patient),
        dob_display=long_date(patient.get("dob")) or "date unknown",
        last_review_display=month_year(patient.get("last_review")) or "none recorded",
        review_overdue=review_overdue(patient),
        months_since_review=months_since(patient["last_review"]) if patient.get("last_review") else None,
        pharmacy_name=pharmacy["name"] if pharmacy else "No pharmacy chosen",
        prescriptions=current_prescriptions(data, patient_id),
        pending=pending,
        active="patients",
    )


@doctor_bp.route("/patients/<patient_id>/prescriptions/<prescription_id>/renew", methods=["POST"])
def renew_from_profile(patient_id, prescription_id):
    data = load_data()
    doc = current_doctor(data)
    if doc is None:
        return redirect(url_for("doctor.login"))

    patient = my_patient(data, doc, patient_id)
    if patient is None:
        flash("That patient isn't registered with you.", "error")
        return redirect(url_for("doctor.patients"))

    old = find(data.get("prescriptions", []), "id", prescription_id)
    if old is None or old.get("patient_id") != patient_id:
        flash("That prescription doesn't belong to this patient.", "error")
        return redirect(url_for("doctor.patient_profile", patient_id=patient_id))
    if old.get("status") == "replaced":
        flash("That prescription has already been renewed.", "error")
        return redirect(url_for("doctor.patient_profile", patient_id=patient_id))

    months = RENEWAL_MONTHS.get(request.form.get("months", ""))
    if months is None:
        flash("Choose how long to renew the prescription for.", "error")
        return redirect(url_for("doctor.patient_profile", patient_id=patient_id))

    today = date.today()
    now = datetime.now()
    expiry = add_months(today, months)
    old["status"] = "replaced"
    data["prescriptions"].append({
        "id": f"rx{now.strftime('%H%M%S%f')}",
        "patient_id": patient_id,
        "doctor_id": doc["id"],
        "medication": old.get("medication", ""),
        "dosage": old.get("dosage", ""),
        "issued_at": today.isoformat(),
        "expiry_date": expiry.isoformat(),
        "repeats_total": months,
        "repeats_left": months,
        "status": "active",
    })

    for renewal in data.get("renewal_requests", []):
        if (
            renewal.get("patient_id") == patient_id
            and renewal.get("medication") == old.get("medication")
            and renewal.get("status") == "pending"
        ):
            renewal["status"] = "renewed"
            renewal["renewed_months"] = months
            renewal["decided_at"] = now.isoformat(timespec="minutes")
            renewal["decided_by"] = doc["id"]

    save_data(data)
    flash(f"Renewed {old.get('medication')} for {full_name(patient)} until {long_date(expiry.isoformat())}.", "success")
    return redirect(url_for("doctor.patient_profile", patient_id=patient_id))