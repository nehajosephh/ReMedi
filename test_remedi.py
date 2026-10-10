
"""Automated tests for ReMedi - HackUCD 2026.

Run from the project folder:
    python -m unittest -v test_remedi.py

Uses synthetic test data. Does not modify the real data/data.json.
"""

import copy
import re
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from flask import Flask

from routes.pharmacy import pharmacy_bp
from services import storage


ROOT = Path(__file__).resolve().parent


def sample_data():
    """Create synthetic records for testing."""
    return {
        "pharmacies": [
            {"id": "ph1", "name": "Griffith Pharmacy"},
            {"id": "ph2", "name": "Drumcondra Pharmacy"},
        ],
        "pharmacists": [
            {
                "id": "s1",
                "psi_number": "8812",
                "name": "Siobhan",
                "pharmacy_id": "ph1",
            },
            {
                "id": "s2",
                "psi_number": "9034",
                "name": "Rahul",
                "pharmacy_id": "ph2",
            },
        ],
        "doctors": [
            {"id": "d1", "name": "Dr Kelly"},
        ],
        "patients": [
            {
                "id": "p1",
                "first_name": "Mary",
                "last_name": "O'Brien",
                "pharmacy_id": "ph1",
                "doctor_id": "d1",
            },
            {
                "id": "p2",
                "first_name": "Sam",
                "last_name": "Example",
                "pharmacy_id": "ph2",
                "doctor_id": "d1",
            },
        ],
        "orders": [],
        "prescriptions": [],
        "renewal_requests": [],
    }


class PharmacyTests(unittest.TestCase):

    def setUp(self):
        """Prepare a fresh fake database before each test."""
        self.data = sample_data()

        self.app = Flask(
            __name__,
            template_folder=str(ROOT / "templates"),
            static_folder=str(ROOT / "static"),
        )

        self.app.config.update(
            TESTING=True,
            SECRET_KEY="test-only-secret",
        )

        self.app.register_blueprint(pharmacy_bp)

        # The real app.py defines this route.
        # Add it here so dashboard templates can render.
        self.app.add_url_rule(
            "/logout",
            endpoint="logout",
            view_func=lambda: "Logged out",
        )

        self.client = self.app.test_client()
        self.saved = []

        # Replace database access with synthetic test data.
        self.load_patch = patch(
            "routes.pharmacy.load_data",
            side_effect=lambda: copy.deepcopy(self.data),
        )

        self.save_patch = patch(
            "routes.pharmacy.save_data",
            side_effect=self._save,
        )

        self.load_patch.start()
        self.save_patch.start()

        self.addCleanup(self.load_patch.stop)
        self.addCleanup(self.save_patch.stop)

    def _save(self, data):
        """Save only to memory, never to data/data.json."""
        self.data = copy.deepcopy(data)
        self.saved.append(copy.deepcopy(data))

    def login(
        self,
        psi="8812",
        pharmacy="ph1",
        password="demo123",
    ):
        return self.client.post(
            "/pharmacy/login",
            data={
                "psi_number": psi,
                "pharmacy_id": pharmacy,
                "password": password,
            },
        )

    def auth_session(
        self,
        pharmacist="s1",
        pharmacy="ph1",
    ):
        """Simulate a logged-in pharmacist."""
        with self.client.session_transaction() as sess:
            sess["role"] = "pharmacy_demo"
            sess["pharmacist_id"] = pharmacist
            sess["pharmacy_id"] = pharmacy

    def request_renewal(self, **overrides):
        payload = {
            "patient_id": "p1",
            "medication": "Metformin 500mg",
            "reason": "last repeat used",
        }

        payload.update(overrides)

        return self.client.post(
            "/pharmacy/request-renewal",
            json=payload,
        )

    # -------------------------------------------
    # LOGIN TESTS
    # -------------------------------------------

    def test_login_page_loads(self):
        response = self.client.get("/pharmacy/login")
        self.assertEqual(response.status_code, 200)

    def test_valid_pharmacist_login_redirects(self):
        response = self.login()

        self.assertEqual(response.status_code, 302)

        with self.client.session_transaction() as sess:
            self.assertEqual(
                sess.get("role"), "pharmacy_demo"
            )
            self.assertEqual(
                sess.get("pharmacy_id"), "ph1"
            )
            self.assertEqual(
                sess.get("pharmacist_id"), "s1"
            )

    def test_invalid_password_does_not_login(self):
        response = self.login(password="incorrect")

        self.assertEqual(response.status_code, 200)

        with self.client.session_transaction() as sess:
            self.assertNotEqual(
                sess.get("role"), "pharmacy_demo"
            )

    def test_wrong_pharmacy_does_not_login(self):
        response = self.login(pharmacy="ph2")

        self.assertEqual(response.status_code, 200)

        with self.client.session_transaction() as sess:
            self.assertNotEqual(
                sess.get("role"), "pharmacy_demo"
            )

    def test_unknown_pharmacist_does_not_login(self):
        response = self.login(psi="0000")
        self.assertEqual(response.status_code, 200)

    # -------------------------------------------
    # DASHBOARD TESTS
    # -------------------------------------------

    def test_dashboard_requires_login(self):
        response = self.client.get("/pharmacy/")
        self.assertEqual(response.status_code, 302)

    def test_dashboard_rejects_invalid_session(self):
        self.auth_session(pharmacist="missing")

        response = self.client.get("/pharmacy/")
        self.assertEqual(response.status_code, 302)

    def test_dashboard_renders_for_valid_pharmacist(self):
        self.auth_session()

        response = self.client.get("/pharmacy/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            b"Griffith Pharmacy",
            response.data,
        )

    # -------------------------------------------
    # RENEWAL AUTHENTICATION TESTS
    # -------------------------------------------

    def test_renewal_requires_authentication(self):
        response = self.request_renewal()

        self.assertEqual(response.status_code, 401)
        self.assertEqual(len(self.saved), 0)

    def test_renewal_rejects_invalid_pharmacist(self):
        self.auth_session(pharmacist="unknown")

        response = self.request_renewal()

        self.assertEqual(response.status_code, 403)

    # -------------------------------------------
    # RENEWAL VALIDATION TESTS
    # -------------------------------------------

    def test_renewal_requires_all_fields(self):
        self.auth_session()

        for key in (
            "patient_id",
            "medication",
            "reason",
        ):
            with self.subTest(field=key):
                response = self.request_renewal(
                    **{key: ""}
                )

                self.assertEqual(
                    response.status_code, 400
                )

        self.assertEqual(len(self.saved), 0)

    def test_renewal_rejects_non_json_body(self):
        self.auth_session()

        response = self.client.post(
            "/pharmacy/request-renewal",
            data="not json",
            content_type="text/plain",
        )

        self.assertEqual(response.status_code, 400)

    def test_renewal_rejects_unknown_patient(self):
        self.auth_session()

        response = self.request_renewal(
            patient_id="missing"
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(len(self.saved), 0)

    def test_renewal_rejects_other_pharmacy_patient(self):
        self.auth_session()

        response = self.request_renewal(
            patient_id="p2"
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(len(self.saved), 0)

    def test_renewal_rejects_missing_gp(self):
        self.auth_session()

        self.data["patients"][0]["doctor_id"] = "missing"

        response = self.request_renewal()

        self.assertEqual(response.status_code, 400)
        self.assertEqual(len(self.saved), 0)

    # -------------------------------------------
    # SUCCESSFUL RENEWAL TESTS
    # -------------------------------------------

    def test_successful_renewal_is_saved(self):
        self.auth_session()

        response = self.request_renewal()

        self.assertEqual(response.status_code, 201)

        body = response.get_json()
        self.assertTrue(body["success"])

        renewal = self.data["renewal_requests"][0]

        self.assertEqual(
            renewal["patient_id"], "p1"
        )
        self.assertEqual(
            renewal["doctor_id"], "d1"
        )
        self.assertEqual(
            renewal["pharmacy_id"], "ph1"
        )
        self.assertEqual(
            renewal["status"], "pending"
        )

        self.assertTrue(
            renewal["id"].startswith("r")
        )

        self.assertEqual(len(self.saved), 1)

    def test_renewal_trims_extra_spaces(self):
        self.auth_session()

        response = self.request_renewal(
            medication="  Metformin 500mg  ",
            reason="  last repeat used  ",
        )

        self.assertEqual(response.status_code, 201)

        renewal = self.data["renewal_requests"][0]

        self.assertEqual(
            renewal["medication"],
            "Metformin 500mg",
        )
        self.assertEqual(
            renewal["reason"],
            "last repeat used",
        )

    # -------------------------------------------
    # DUPLICATE PREVENTION TESTS
    # -------------------------------------------

    def test_duplicate_pending_renewal_rejected(self):
        self.auth_session()

        first = self.request_renewal()
        self.assertEqual(first.status_code, 201)

        second = self.request_renewal(
            medication="METFORMIN 500MG"
        )

        self.assertEqual(second.status_code, 409)

        self.assertEqual(
            len(self.data["renewal_requests"]), 1
        )

        self.assertEqual(len(self.saved), 1)

    def test_old_declined_renewal_allows_new_request(self):
        self.auth_session()

        self.data["renewal_requests"].append({
            "id": "r-old",
            "patient_id": "p1",
            "medication": "Metformin 500mg",
            "status": "declined",
        })

        response = self.request_renewal()

        self.assertEqual(response.status_code, 201)

        self.assertEqual(
            len(self.data["renewal_requests"]), 2
        )

    # -------------------------------------------
    # MULTIPLE PHARMACY TEST
    # -------------------------------------------

    def test_second_pharmacy_can_request_renewal(self):
        self.auth_session(
            pharmacist="s2",
            pharmacy="ph2",
        )

        response = self.request_renewal(
            patient_id="p2"
        )

        self.assertEqual(response.status_code, 201)

        self.assertEqual(
            self.data["renewal_requests"][0]["pharmacy_id"],
            "ph2",
        )

    # -------------------------------------------
    # HTTP METHOD TESTS
    # -------------------------------------------

    def test_get_not_allowed_for_renewal(self):
        self.auth_session()

        response = self.client.get(
            "/pharmacy/request-renewal"
        )

        self.assertEqual(response.status_code, 405)

    def test_failed_request_does_not_save_data(self):
        self.auth_session()

        response = self.request_renewal(reason="")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.saved, [])


class StorageTests(unittest.TestCase):

    def test_find_by_returns_matching_record(self):
        records = [
            {"id": "a"},
            {"id": "b"},
        ]

        result = storage.find_by(
            records, "id", "b"
        )

        self.assertEqual(result, {"id": "b"})

    def test_find_by_returns_none_if_missing(self):
        result = storage.find_by(
            [{"id": "a"}],
            "id",
            "missing",
        )

        self.assertIsNone(result)

    def test_storage_save_and_load(self):
        with TemporaryDirectory() as folder:
            target = str(Path(folder) / "data.json")

            with patch.object(
                storage, "DATA_FILE", target
            ):
                storage.save_data({
                    "patients": [
                        {"name": "Siobhán"}
                    ]
                })

                loaded = storage.load_data()

                self.assertEqual(
                    loaded["patients"][0]["name"],
                    "Siobhán",
                )

    def test_login_required_protects_route(self):
        app = Flask(__name__)
        app.config["SECRET_KEY"] = "test-secret"

        @app.route("/")
        def welcome():
            return "welcome"

        @app.route("/protected")
        @storage.login_required("doctor")
        def protected():
            return "private"

        client = app.test_client()

        response = client.get("/protected")
        self.assertEqual(response.status_code, 302)

        with client.session_transaction() as sess:
            sess["role"] = "doctor"

        response = client.get("/protected")
        self.assertEqual(response.status_code, 200)


class TemplateConsistencyTests(unittest.TestCase):

    def test_doctor_template_includes_exist(self):
        folder = ROOT / "templates" / "doctor"

        if not folder.is_dir():
            self.skipTest(
                "GP templates not present"
            )

        for template in folder.glob("*.html"):
            contents = template.read_text(
                encoding="utf-8"
            )

            includes = re.findall(
                r'{%\s*include\s+[\'"]'
                r'(doctor/[^\'"]+)'
                r'[\'"]\s*%}',
                contents,
            )

            for name in includes:
                with self.subTest(
                    template=template.name,
                    included=name,
                ):
                    self.assertTrue(
                        (ROOT / "templates" / name).is_file(),
                        f"{template.name} includes missing "
                        f"template: {name}",
                    )

    def test_pharmacy_template_assets_exist(self):
        assets = (
            "templates/pharmacy/login.html",
            "templates/pharmacy/dashboard.html",
            "static/js/pharmacy.js",
            "static/css/pharmacy.css",
        )

        for asset in assets:
            with self.subTest(asset=asset):
                self.assertTrue(
                    (ROOT / asset).is_file(),
                    f"Missing: {asset}",
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
