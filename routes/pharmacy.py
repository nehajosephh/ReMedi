import json
from pathlib import Path

from flask import (
    Blueprint, render_template, request,
    redirect, url_for, session
)

pharmacy_bp = Blueprint(
    "pharmacy",
    __name__,
    url_prefix="/pharmacy"
)

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "data.json"


def load_data():
    with open(DATA_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


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

        pharmacist = next(
            (
                person for person in pharmacists
                if person["psi_number"] == psi_number
                and person["pharmacy_id"] == pharmacy_id
            ),
            None
        )

        # Hackathon demo authentication only.
        # This does not verify registration with the PSI.
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


@pharmacy_bp.route("/")
def dashboard():
    if session.get("role") != "pharmacy_demo":
        return redirect(url_for("pharmacy.login"))

    data = load_data()

    pharmacy_id = session.get("pharmacy_id")
    pharmacist_id = session.get("pharmacist_id")

    pharmacy = next(
        (p for p in data.get("pharmacies", [])
         if p["id"] == pharmacy_id),
        None
    )

    pharmacist = next(
        (p for p in data.get("pharmacists", [])
         if p["id"] == pharmacist_id
         and p["pharmacy_id"] == pharmacy_id),
        None
    )

    if not pharmacy or not pharmacist:
        session.clear()
        return redirect(url_for("pharmacy.login"))

    patients = [
        patient for patient in data.get("patients", [])
        if patient.get("pharmacy_id") == pharmacy_id
    ]

    orders = [
        order for order in data.get("orders", [])
        if order.get("pharmacy_id") == pharmacy_id
    ]

    renewals = [
        renewal for renewal in data.get("renewal_requests", [])
        if renewal.get("pharmacy_id") == pharmacy_id
    ]

    patient_lookup = {
        patient["id"]: patient
        for patient in data.get("patients", [])
    }

    doctor_lookup = {
        doctor["id"]: doctor
        for doctor in data.get("doctors", [])
    }

    for renewal in renewals:
        renewal["patient"] = patient_lookup.get(
            renewal.get("patient_id"), {}
        )

    return render_template(
        "pharmacy/dashboard.html",
        pharmacy=pharmacy,
        pharmacist=pharmacist,
        patients=patients,
        orders=orders,
        renewals=renewals,
        doctor_lookup=doctor_lookup,
        pending_renewals=sum(
            r.get("status") == "pending" for r in renewals
        )
    )