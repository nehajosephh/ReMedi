import os

from dotenv import load_dotenv
from flask import Flask, redirect, render_template, session, url_for

from routes.doctor import doctor_bp
from routes.patient import patient_bp
from routes.pharmacy import pharmacy_bp

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-only-change-me")

app.register_blueprint(patient_bp)    # Neha:  routes/patient.py
app.register_blueprint(doctor_bp)     # Nidhy: routes/doctor.py
app.register_blueprint(pharmacy_bp)   # Aadya: routes/pharmacy.py


@app.route("/")
def welcome():
    role = session.get("role")
    if role:  # already logged in, skip the welcome screen
        return redirect(url_for(f"{role}.home"))
    return render_template("welcome.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("welcome"))


if __name__ == "__main__":
    app.run(debug=True, port=5001)