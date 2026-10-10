# ReMedi

### Connecting patients, GPs and pharmacies. Simplifying prescription management.

**Built for HackUCD 2026**

ReMedi is a web-based prescription management platform designed to streamline communication between patients, general practitioners (GPs) and pharmacists.

By bringing all three stakeholders together in one connected system, ReMedi aims to reduce administrative delays, simplify prescription renewals and make medication management more accessible.

**Our mission:** Less prescription paperwork. More time for care.

---

## The Problem

Managing repeat prescriptions can be unnecessarily complicated.

Patients may need to contact their GP, coordinate with their pharmacy, track when their medication is due and arrange payment, often across disconnected systems.

Meanwhile, GPs and pharmacists spend valuable time processing renewal requests and coordinating prescriptions.

These challenges can create:

- Delays in prescription renewals.
- Unnecessary communication between patients, GPs and pharmacies.
- Limited visibility into prescription and order statuses.
- Additional administrative work for healthcare professionals.
- Confusion around prescription costs and payments.

## Our Solution

ReMedi provides three interconnected portals that support the prescription journey from GP review to pharmacy fulfilment and patient payment.

Rather than requiring patients to coordinate each stage independently, ReMedi brings the process into one platform.

## Key Features

### Patient Portal

The patient-facing interface provides a central location for managing prescriptions and medication orders.

Features include:

- Viewing medication and prescription information.
- Requesting medication orders.
- Tracking order progress.
- Viewing prescription renewal information.
- Accessing invoices and payment options.
- Managing pharmacy-related information.

### GP Portal

The GP portal helps doctors manage prescription requests and patient information.

Features include:

- Viewing assigned patients.
- Reviewing incoming prescription renewal requests.
- Creating new prescriptions.
- Renewing prescriptions for selected durations.
- Requesting patient reviews.
- Declining renewal requests with a reason.
- Viewing relevant patient information.

### Pharmacist Portal

The pharmacist dashboard supports prescription processing, renewal coordination and order management.

Features include:

- Viewing incoming patient orders.
- Reviewing requested medications.
- Identifying prescriptions requiring attention.
- Sending renewal requests to the patient's GP.
- Tracking pending prescription renewals.
- Managing pharmacy fulfilment workflows.
- Calculating prescription costs.
- Generating patient invoices.
- Supporting different payment categories, including private payment, Medical Card and the Drugs Payment Scheme.

### Payments and Invoicing

ReMedi includes an invoicing and payment workflow designed to help patients understand their prescription costs.

The application incorporates Stripe for payment processing in a demonstration environment.

### AI Integration

ReMedi incorporates an OpenRouter-powered AI component as part of its prototype.

AI functionality is intended to support the user experience and assist with relevant application workflows. It is not a substitute for professional medical judgment or prescription authorisation.

---

## How ReMedi Works

1. **Patient:** A patient views their medication information and places an order or requests a renewal.
2. **Pharmacy:** The pharmacist reviews the order and identifies any prescriptions requiring GP attention.
3. **GP:** The GP receives the renewal request and decides whether to renew, request a review or decline.
4. **Pharmacy:** The pharmacy processes the order and prepares the associated invoice.
5. **Patient:** The patient can review their order information and proceed through the available payment workflow.

The three portals operate through a shared backend, allowing information to move between different parts of the application.

---

## Tech Stack

| Technology | Purpose |
|---|---|
| Python | Backend development |
| Flask | Web application framework and routing |
| HTML | Page structure |
| CSS | Interface design and responsive styling |
| JavaScript | Frontend interactions |
| JSON | Prototype data storage |
| Stripe | Payment integration |
| OpenRouter | AI integration |
| Git and GitHub | Version control and team collaboration |
| Python unittest | Automated testing |

## Project Structure

The main components of the application are organised as follows:

```text
ReMedi/
├── app.py
├── routes/
│   ├── doctor.py
│   ├── patient.py
│   ├── pharmacy.py
│   └── payments.py
├── services/
│   ├── storage.py
│   ├── ai_assistant.py
│   ├── medication_catalogue.py
│   └── prescription_rules.py
├── templates/
│   ├── doctor/
│   ├── patient/
│   └── pharmacy/
├── static/
│   ├── css/
│   └── js/
├── data/
│   └── data.json
├── test_remedi.py
├── requirements.txt
└── README.md
```

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/nehajosephh/ReMedi.git
cd ReMedi
```

### 2. Create a virtual environment

```bash
python3 -m venv .venv
```

Activate it on macOS or Linux:

```bash
source .venv/bin/activate
```

On Windows:

```bash
.venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Create a `.env` file in the project root if required by the enabled integrations.

Add the necessary development API keys and settings for the application's AI and payment services, using the variable names expected by the source code.

Never commit real API keys, passwords or secrets to GitHub.

### 5. Start the application

```bash
python app.py
```

Open the local development server:

http://127.0.0.1:5001

### 6. Explore ReMedi

From the welcome page, select the relevant portal:

- Patient
- GP
- Pharmacist

Use the synthetic demo accounts configured in the application.

---

## Testing

ReMedi includes automated tests covering key pharmacist workflows and shared application functionality.

The test suite checks:

- Pharmacist login and authentication.
- Dashboard access restrictions.
- Prescription renewal request validation.
- Successful renewal request creation.
- Prevention of duplicate pending requests.
- Pharmacy-specific access controls.
- Shared JSON storage functions.
- Template and static asset availability.

Run the tests from the project directory:

```bash
python -m unittest -v test_remedi.py
```

Tests use synthetic data and mock database operations to avoid modifying the application's main demo records.

## Privacy and Safety

**ReMedi is a hackathon prototype, not a production healthcare system.**

All patient records, healthcare professionals, pharmacies, registration numbers and prescriptions included in the demonstration are synthetic.

The prototype is intended to demonstrate a possible digital workflow rather than provide real clinical services.

A production deployment would require additional work, including:

- Secure authentication and authorisation.
- Encrypted data storage and appropriate privacy controls.
- GDPR compliance and healthcare data governance.
- Verification of healthcare professionals and prescriptions.
- Clinical safety validation.
- Integration with authorised healthcare systems.
- Secure payment configuration and testing.

AI-generated information must not be treated as medical advice or used to independently authorise prescriptions.

## Future Development

Potential next steps include:

- Integration with authorised electronic prescribing systems.
- Automated reminders for upcoming prescription renewals.
- Patient notifications when orders are ready.
- More comprehensive prescription status tracking.
- Secure messaging between patients and healthcare professionals.
- Enhanced accessibility features.
- Expanded testing across all three portals.
- Production-ready data storage and security controls.

## HackUCD 2026

ReMedi was developed as a collaborative hackathon project, combining software engineering, user-centred design and healthcare workflow innovation.

Our focus was to demonstrate how technology could connect patients, GPs and pharmacists through a simpler, more transparent prescription management experience.

## Our Vision

Healthcare professionals should be able to spend more time caring for patients and less time coordinating paperwork.

Patients should have a clearer understanding of their prescriptions, orders and payments.

**ReMedi brings these goals together in one connected experience.**

### ReMedi: Less prescription paperwork. More time for care.
