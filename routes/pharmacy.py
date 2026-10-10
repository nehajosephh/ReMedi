
from flask import Blueprint, render_template, request, redirect, url_for, session

pharmacy_bp = Blueprint(
    "pharmacy",
    __name__,
    url_prefix="/pharmacy"
)

@pharmacy_bp.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":
        psi = request.form.get("psi", "").strip()
        pharmacy = request.form.get("pharmacy", "")
        password = request.form.get("password", "")

        # Hackathon demo only: no real PSI verification yet.
        if psi and pharmacy and password:
            session["role"] = "pharmacy_demo"
            return redirect(url_for("pharmacy.dashboard"))

    return render_template("pharmacy/login.html")


@pharmacy_bp.route("/")
def dashboard():
    if session.get("role") != "pharmacy_demo":
        return redirect(url_for("pharmacy.login"))

    return render_template("pharmacy/dashboard.html")
