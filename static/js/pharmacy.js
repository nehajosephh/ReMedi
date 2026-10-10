
/* =========================================
   REMEDI PHARMACY DASHBOARD
   Data supplied by Flask from data.json
   ========================================= */

const dataElement = document.getElementById("pharmacy-data");

if (dataElement) {
    const pharmacyData = JSON.parse(dataElement.textContent);

    const orders = pharmacyData.orders || [];
    const patients = pharmacyData.patients || [];
    const renewals = pharmacyData.renewals || [];
    const doctors = pharmacyData.doctors || {};

    const ordersList = document.getElementById("orders-list");
    const detailsPanel = document.getElementById("order-details");

    let selectedOrderId = null;

    // Escape user-provided text before inserting into HTML.
    function escapeHTML(value) {
        return String(value ?? "").replace(/[&<>"']/g, char => ({
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#39;"
        }[char]));
    }

    function displayStatus(status) {
        return String(status || "Unknown")
            .replace(/_/g, " ")
            .replace(/\b\w/g, letter => letter.toUpperCase());
    }

    function statusClass(status) {
        if (["needs_attention", "expired", "pending"].includes(status)) {
            return "status-warning";
        }

        if (["ready", "approved", "completed"].includes(status)) {
            return "status-success";
        }

        return "status-neutral";
    }

    function getPatient(patientId) {
        return patients.find(patient => patient.id === patientId) || {};
    }

    function getDoctor(doctorId) {
        return doctors[doctorId] || {};
    }

    function getPatientName(patient) {
        if (!patient.first_name) {
            return "Unknown patient";
        }

        return `${patient.first_name} ${patient.last_name || ""}`.trim();
    }

    function formatDate(dateValue) {
        if (!dateValue) return "Not specified";

        const date = new Date(dateValue);

        if (Number.isNaN(date.getTime())) {
            return String(dateValue);
        }

        return date.toLocaleDateString("en-IE", {
            day: "numeric",
            month: "short",
            year: "numeric"
        });
    }

    function formatTime(dateValue) {
        if (!dateValue) return "";

        const match = String(dateValue).match(/T(\d{2}:\d{2})/);
        return match ? match[1] : "";
    }

    function getRelatedRenewals(patientId) {
        return renewals.filter(
            renewal => renewal.patient_id === patientId
        );
    }

    // Orders are displayed chronologically.
    orders.sort((a, b) =>
        String(a.created_at || "").localeCompare(
            String(b.created_at || "")
        )
    );

    function renderOrders() {
        if (!ordersList || orders.length === 0) return;

        ordersList.innerHTML = "";

        orders.forEach(order => {
            const patient = getPatient(order.patient_id);
            const name = getPatientName(patient);

            const button = document.createElement("button");
            button.type = "button";

            button.className = "order-item";

            if (order.id === selectedOrderId) {
                button.classList.add("active");
            }

            button.innerHTML = `
                <div class="order-top">
                    <strong>${escapeHTML(name)}</strong>
                    <span class="order-time">
                        ${escapeHTML(formatTime(order.created_at))}
                    </span>
                </div>

                <p class="order-subtitle">
                    ${escapeHTML(patient.scheme || "Patient order")}
                    · ${escapeHTML(displayStatus(order.fulfilment))}
                </p>

                <div class="order-bottom">
                    <span class="status-pill ${statusClass(order.status)}">
                        ${escapeHTML(displayStatus(order.status))}
                    </span>

                    <small>${escapeHTML(order.id)}</small>
                </div>
            `;

            button.addEventListener("click", () => {
                selectedOrderId = order.id;
                renderOrders();
                renderDetails(order);
            });

            ordersList.appendChild(button);
        });
    }

    function renderDetails(order) {
        if (!detailsPanel) return;

        const patient = getPatient(order.patient_id);
        const doctor = getDoctor(patient.doctor_id);
        const relatedRenewals = getRelatedRenewals(patient.id);

        const orderItems = Array.isArray(order.items)
            ? order.items
            : [];

        const hasRenewal = relatedRenewals.some(
            renewal => renewal.status === "pending"
        );

        const hasAttention = order.status === "needs_attention";

        // No automatic approval of flagged orders.
        const canApprove = !hasAttention
            && !hasRenewal
            && order.status === "pending"
            && orderItems.length > 0;

        const renewalWarning = relatedRenewals.length
            ? relatedRenewals.map(renewal => `
                <div class="warning-banner">
                    <strong>Prescription renewal:</strong>
                    ${escapeHTML(renewal.medication)}
                    <br>
                    Reason: ${escapeHTML(renewal.reason)}
                    <br>
                    Status: ${escapeHTML(displayStatus(renewal.status))}
                </div>
            `).join("")
            : "";

        const itemsHTML = orderItems.length
            ? orderItems.map(item => {
                const name = item.medicine_name
                    || item.name
                    || item.medication
                    || "Unknown medication";

                const quantity = item.quantity ?? "Not specified";

                const relatedRenewal = relatedRenewals.find(
                    renewal =>
                        String(renewal.medication || "").toLowerCase()
                        === String(name).toLowerCase()
                );

                const medicationStatus = relatedRenewal
                    ? "Renewal requested"
                    : "Requires pharmacist review";

                return `
                    <tr>
                        <td>${escapeHTML(name)}</td>
                        <td>${escapeHTML(quantity)}</td>
                        <td>
                            <span class="status-pill ${
                                relatedRenewal
                                    ? "status-warning"
                                    : "status-neutral"
                            }">
                                ${escapeHTML(medicationStatus)}
                            </span>
                        </td>
                    </tr>
                `;
            }).join("")
            : `
                <tr>
                    <td colspan="3">
                        No medication items recorded.
                    </td>
                </tr>
            `;

        const patientMessage = order.patient_message
            ? escapeHTML(order.patient_message)
            : "No patient message provided.";

        detailsPanel.innerHTML = `
            <div class="patient-heading">
                <div>
                    <h2>${escapeHTML(getPatientName(patient))}</h2>
                    <p>
                        Order ${escapeHTML(order.id)}
                        · ${escapeHTML(formatDate(order.created_at))}
                    </p>
                </div>

                <span class="status-pill ${statusClass(order.status)}">
                    ${escapeHTML(displayStatus(order.status))}
                </span>
            </div>

            <div class="detail-grid">
                <div class="detail-box">
                    <span>Payment scheme</span>
                    <strong>
                        ${escapeHTML(patient.scheme || "Not specified")}
                    </strong>
                </div>

                <div class="detail-box">
                    <span>Delivery / collection</span>
                    <strong>
                        ${escapeHTML(displayStatus(order.fulfilment))}
                    </strong>
                </div>

                <div class="detail-box">
                    <span>Requested date</span>
                    <strong>
                        ${escapeHTML(formatDate(order.delivery_date))}
                    </strong>
                </div>

                <div class="detail-box">
                    <span>Preferred time</span>
                    <strong>
                        ${escapeHTML(displayStatus(order.delivery_slot))}
                    </strong>
                </div>

                <div class="detail-box">
                    <span>GP</span>
                    <strong>
                        ${escapeHTML(doctor.name || "Not specified")}
                    </strong>
                </div>

                <div class="detail-box">
                    <span>GP practice</span>
                    <strong>
                        ${escapeHTML(doctor.practice || "Not specified")}
                    </strong>
                </div>
            </div>

            <h3 class="section-title">Patient request</h3>

            <div class="ai-summary">
                <strong>Original patient message</strong>
                <p>${patientMessage}</p>
            </div>

            <p class="ai-disclaimer">
                AI interpretation is not connected yet.
                Always review the original request.
            </p>

            ${renewalWarning}

            <h3 class="section-title">Medication review</h3>

            <div class="table-wrapper">
                <table class="medicine-table">
                    <thead>
                        <tr>
                            <th>Medication</th>
                            <th>Requested quantity</th>
                            <th>Review status</th>
                        </tr>
                    </thead>

                    <tbody>
                        ${itemsHTML}
                    </tbody>
                </table>
            </div>

            <div class="dashboard-actions">
                <button type="button"
                        class="primary-button"
                        id="approve-btn"
                        ${canApprove ? "" : "disabled"}>
                    Approve and pack
                </button>

                <button type="button"
                        class="secondary-button"
                        id="renewal-btn">
                    Send renewal request to GP
                </button>

                <button type="button"
                        class="secondary-button"
                        id="message-btn">
                    Message patient
                </button>
            </div>

            <div class="action-feedback"
                 id="action-feedback"
                 role="status"
                 aria-live="polite"></div>
        `;

        attachActions(order, canApprove);
    }

    function attachActions(order, canApprove) {
        const approveButton = document.getElementById("approve-btn");
        const renewalButton = document.getElementById("renewal-btn");
        const messageButton = document.getElementById("message-btn");
        const feedback = document.getElementById("action-feedback");

        approveButton.addEventListener("click", () => {
            if (!canApprove) return;

            feedback.textContent =
                "Demo only: no approval has been saved. " +
                "Backend pharmacist review is not connected yet.";
        });

        // Open the prescription renewal form.
        renewalButton.addEventListener("click", () => {
            const patient = getPatient(order.patient_id);

            const orderItems = Array.isArray(order.items)
                ? order.items
                : [];

            const names = [
                ...new Set(
                    orderItems.map(item =>
                        String(
                            item.medicine_name
                            || item.name
                            || item.medication
                            || ""
                        ).trim()
                    ).filter(Boolean)
                )
            ];

            // Use medications from the selected order.
            const options = names.map(name =>
                `<option value="${escapeHTML(name)}">
                    ${escapeHTML(name)}
                </option>`
            ).join("");

            feedback.innerHTML = `
                <form id="send-renewal-form"
                      class="renewal-info"
                      style="display:grid;gap:12px;margin-top:12px;text-align:left">

                    <strong>
                        Renewal request for
                        ${escapeHTML(getPatientName(patient))}
                    </strong>

                    <label for="renewal-medication">
                        Medication
                    </label>

                    ${names.length ? `
                        <select id="renewal-medication"
                                required
                                style="width:100%;padding:10px;border-radius:8px">
                            <option value="">Select medication</option>
                            ${options}
                        </select>
                    ` : `
                        <input id="renewal-medication"
                               required
                               maxlength="160"
                               placeholder="Medication and strength"
                               style="width:100%;padding:10px;border-radius:8px">
                    `}

                    <label for="renewal-reason">
                        Reason
                    </label>

                    <select id="renewal-reason"
                            required
                            style="width:100%;padding:10px;border-radius:8px">

                        <option value="">Select reason</option>

                        <option value="script expired">
                            Prescription expired
                        </option>

                        <option value="last repeat used">
                            Last repeat used
                        </option>

                        <option value="patient requested renewal">
                            Patient requested renewal
                        </option>
                    </select>

                    <button type="submit"
                            class="primary-button"
                            id="submit-renewal">
                        Submit request for GP review
                    </button>

                    <p id="renewal-result"
                       role="status"
                       aria-live="polite"></p>
                </form>
            `;

            // Submit the renewal request to Flask.
            document.getElementById("send-renewal-form")
                .addEventListener("submit", async event => {

                    event.preventDefault();

                    const submitButton =
                        document.getElementById("submit-renewal");

                    const result =
                        document.getElementById("renewal-result");

                    const medication =
                        document.getElementById("renewal-medication")
                            .value.trim();

                    const reason =
                        document.getElementById("renewal-reason").value;

                    if (!medication || !reason) return;

                    // Check for an existing pending request.
                    const alreadyPending = getRelatedRenewals(
                        order.patient_id
                    ).some(renewal =>
                        renewal.status === "pending"
                        && String(renewal.medication || "")
                            .trim()
                            .toLowerCase() === medication.toLowerCase()
                    );

                    if (alreadyPending) {
                        result.textContent =
                            "A pending renewal already exists " +
                            "for this medication.";
                        return;
                    }

                    submitButton.disabled = true;
                    result.textContent = "Sending request...";

                    try {
                        const response = await fetch(
                            "/pharmacy/request-renewal",
                            {
                                method: "POST",
                                headers: {
                                    "Content-Type": "application/json"
                                },
                                body: JSON.stringify({
                                    patient_id: order.patient_id,
                                    medication: medication,
                                    reason: reason
                                })
                            }
                        );

                        const payload = await response.json();

                        if (!response.ok) {
                            result.textContent =
                                payload.error || "Unable to submit request.";

                            submitButton.disabled = false;
                            return;
                        }

                        result.textContent =
                            "Saved! Renewal is now pending GP review.";

                        // Refresh renewal cards and summary counts.
                        window.location.reload();

                    } catch (error) {
                        result.textContent =
                            "Could not contact the server. Please try again.";

                        submitButton.disabled = false;
                        console.error(error);
                    }
                });
        });

        messageButton.addEventListener("click", () => {
            feedback.textContent =
                "Demo only: patient messaging is not connected yet.";
        });
    }

    // Existing renewal cards are informational for now.
    document.querySelectorAll(".renewal-demo-btn").forEach(button => {
        button.addEventListener("click", () => {
            button.textContent = "Request shown above";
        });
    });

    // Automatically select the oldest order.
    if (orders.length > 0) {
        selectedOrderId = orders[0].id;
        renderOrders();
        renderDetails(orders[0]);
    }
}
