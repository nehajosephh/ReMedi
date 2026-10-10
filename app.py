import os

from dotenv import load_dotenv
from flask import Flask, redirect, render_template, session, url_for

from routes.patient import patient_bp

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-only-change-me")

app.register_blueprint(patient_bp)  # Neha: routes/patient.py

# Nidhy's and Aadya's sections load automatically once their files have a blueprint in them
try:
    from routes.doctor import doctor_bp
    app.register_blueprint(doctor_bp)
except ImportError:
    print("GP section not ready yet, skipping")

from routes.payments import payments_bp
app.register_blueprint(payments_bp)   # Stripe invoices: routes/payments.py

try:
    from routes.pharmacy import pharmacy_bp
    app.register_blueprint(pharmacy_bp)
except ImportError:
    print("Pharmacy section not ready yet, skipping")


@app.route("/")
def welcome():
    # Already signed in? Go straight to your own section.
    home_pages = {"patient": "patient.home", "doctor": "doctor.home", "pharmacy_demo": "pharmacy.dashboard"}
    role = session.get("role")
    if role in home_pages:
        return redirect(url_for(home_pages[role]))
    return render_template("welcome.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("welcome"))


if __name__ == "__main__":
    app.run(debug=True, port=5001)
