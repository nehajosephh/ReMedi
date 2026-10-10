
from datetime import datetime
from uuid import uuid4

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    session,
    jsonify
)

# Shared data functions used by the whole ReMedi team
from services.storage import load_data, save_data


# --------------------------------------------------
# PHARMACY BLUEPRINT
# --------------------------------------------------

pharmacy_bp = Blueprint(
    "pharmacy",
    __name__,
    url_prefix="/pharmacy"
)


# --------------------------------------------------
# PHARMACIST LOGIN
# --------------------------------------------------

@pharmacy_bp.route("/login", methods=["GET", "POST"])
def login():

    data = load_data()

    pharmacies = data.get("pharmacies", [])
    pharmacists = data.get("pharmacists", [])

    error = None

    if request.method == "POST":

        psi_number = request.form.get("psi_number", "").strip()
        pharmacy_id = request.form.get("pharmacy_id", "")
        password = request.form.get("password", "")

        # Find pharmacist matching PSI number and pharmacy
        pharmacist = next(
            (
                person for person in pharmacists
                if person["psi_number"] == psi_number
                and person["pharmacy_id"] == pharmacy_id
            ),
            None
        )

        # Hackathon demo authentication only.
        # This does NOT verify PSI registration.
        if pharmacist and password == "demo123":

            session.clear()

            session["role"] = "pharmacy_demo"
            session["pharmacist_id"] = pharmacist["id"]
            session["pharmacy_id"] = pharmacy_id

            return redirect(url_for("pharmacy.dashboard"))

        error = "Invalid demo credentials or pharmacy selection."

    return render_template(
        "pharmacy/login.html",
        pharmacies=pharmacies,
        error=error
    )


# --------------------------------------------------
# PHARMACIST DASHBOARD
# --------------------------------------------------

@pharmacy_bp.route("/")
def dashboard():

    # Only logged-in pharmacy staff can access
    if session.get("role") != "pharmacy_demo":
        return redirect(url_for("pharmacy.login"))

    data = load_data()

    pharmacy_id = session.get("pharmacy_id")
    pharmacist_id = session.get("pharmacist_id")

    # Find the logged-in pharmacy
    pharmacy = next(
        (
            p for p in data.get("pharmacies", [])
            if p["id"] == pharmacy_id
        ),
        None
    )

    # Find the logged-in pharmacist
    pharmacist = next(
        (
            p for p in data.get("pharmacists", [])
            if p["id"] == pharmacist_id
            and p["pharmacy_id"] == pharmacy_id
        ),
        None
    )

    # Invalid session: return to login
    if not pharmacy or not pharmacist:
        session.clear()
        return redirect(url_for("pharmacy.login"))

    # Only patients registered with this pharmacy
    patients = [
        patient
        for patient in data.get("patients", [])
        if patient.get("pharmacy_id") == pharmacy_id
    ]

    # Only orders belonging to this pharmacy
    orders = [
        order
        for order in data.get("orders", [])
        if order.get("pharmacy_id") == pharmacy_id
    ]

    # Only renewal requests for this pharmacy
    renewals = [
        renewal
        for renewal in data.get("renewal_requests", [])
        if renewal.get("pharmacy_id") == pharmacy_id
    ]

    # Lookups for displaying patient and GP information
    patient_lookup = {
        patient["id"]: patient
        for patient in data.get("patients", [])
    }

    doctor_lookup = {
        doctor["id"]: doctor
        for doctor in data.get("doctors", [])
    }

    # Add patient information to each renewal for display
    for renewal in renewals:
        renewal["patient"] = patient_lookup.get(
            renewal.get("patient_id"), {}
        )

    # Render the existing pharmacist dashboard
    return render_template(
        "pharmacy/dashboard.html",
        pharmacy=pharmacy,
        pharmacist=pharmacist,
        patients=patients,
        orders=orders,
        renewals=renewals,
        doctor_lookup=doctor_lookup,
        pending_renewals=sum(
            r.get("status") == "pending"
            for r in renewals
        )
    )


# --------------------------------------------------
# REQUEST PRESCRIPTION RENEWAL
# --------------------------------------------------

@pharmacy_bp.route("/request-renewal", methods=["POST"])
def request_renewal():

    # Step 1: Check pharmacist is logged in
    if session.get("role") != "pharmacy_demo":
        return jsonify({
            "error": "Please sign in as pharmacy staff."
        }), 401

    # Step 2: Get information sent from dashboard
    details = request.get_json(silent=True) or {}

    patient_id = details.get("patient_id")
    medication = str(details.get("medication", "")).strip()
    reason = str(details.get("reason", "")).strip()

    # Step 3: Check required fields
    if not patient_id or not medication or not reason:
        return jsonify({
            "error": "Missing required information."
        }), 400

    # Step 4: Load shared ReMedi data
    data = load_data()

    # Step 5: Find the patient
    patient = next(
        (
            p for p in data.get("patients", [])
            if p["id"] == patient_id
        ),
        None
    )

    if patient is None:
        return jsonify({
            "error": "Patient not found."
        }), 404

    # Step 6: Check patient belongs to this pharmacy
    pharmacy_id = session.get("pharmacy_id")
    pharmacist_id = session.get("pharmacist_id")

    if (
        not pharmacy_id
        or patient.get("pharmacy_id") != pharmacy_id
    ):
        return jsonify({
            "error": "Patient not assigned to your pharmacy."
        }), 403

    # Check the session still refers to a valid pharmacist
    pharmacist = next(
        (
            p for p in data.get("pharmacists", [])
            if p.get("id") == pharmacist_id
            and p.get("pharmacy_id") == pharmacy_id
        ),
        None
    )

    if pharmacist is None:
        return jsonify({
            "error": "Invalid pharmacist session."
        }), 403

    # Step 7: Find the patient's assigned GP
    doctor_id = patient.get("doctor_id")

    doctor = next(
        (
            d for d in data.get("doctors", [])
            if d["id"] == doctor_id
        ),
        None
    )

    if doctor is None:
        return jsonify({
            "error": "Assigned GP not found."
        }), 400

    # Step 8: Avoid duplicate pending renewal requests
    existing = next(
        (
            r for r in data.get("renewal_requests", [])
            if r.get("patient_id") == patient_id
            and r.get("medication", "").casefold()
            == medication.casefold()
            and r.get("status") == "pending"
        ),
        None
    )

    if existing:
        return jsonify({
            "error": "A pending renewal request already exists."
        }), 409

    # Step 9: Create the new renewal request
    new_request = {
        "id": "r" + uuid4().hex[:8],
        "patient_id": patient_id,
        "pharmacy_id": pharmacy_id,
        "doctor_id": doctor_id,
        "medication": medication,
        "dosage": "",
        "reason": reason,
        "requested_at": datetime.now().isoformat(
            timespec="minutes"
        ),
        "previous_script": "",
        "note": "",
        "status": "pending"
    }

    # Step 10: Add renewal request to shared data
    data.setdefault(
        "renewal_requests", []
    ).append(new_request)

    # Step 11: Save using team's shared storage helper
    save_data(data)

    # Step 12: Send success response to dashboard
    return jsonify({
        "success": True,
        "message": "Renewal request saved for GP review.",
        "request": new_request
    }), 201
