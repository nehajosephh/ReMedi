
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
                        renewal.medication.toLowerCase()
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

            ${invoiceHTML(order)}

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
        attachInvoice(order);
    }

    // ---------- Invoice: pharmacist prices the order, patient pays (Stripe for delivery) ----------
    function euro(cents) {
        return "€" + (Number(cents || 0) / 100).toFixed(2);
    }

    function paymentLabel(order) {
        return {
            not_invoiced: "Not invoiced yet",
            awaiting_payment: "Invoice sent, waiting for card payment",
            pay_in_store: "Pay in store on collection",
            paid: `Paid ${order.paid_by || ""}`.trim()
        }[order.payment_status] || displayStatus(order.payment_status);
    }

    function invoiceHTML(order) {
        const inv = order.invoice;
        const finished = ["delivered", "collected", "cancelled"].includes(order.status);
        const deliveryFee = order.fulfilment === "delivery" ? 300 : 0;

        if (!inv) {
            if (finished) return "";
            return `
                <h3 class="section-title">Price and send invoice</h3>
                <div class="detail-box">
                    <label for="medicines-euro"><span>Prescription charge for this patient's scheme (€)</span></label>
                    <input id="medicines-euro" type="number" min="0" step="0.01" placeholder="e.g. 4.50"
                           style="width:100%;padding:12px;border:1px solid #c9ded0;border-radius:10px;font-size:15px;">
                    <p class="ai-disclaimer">
                        ${deliveryFee ? "€3.00 home delivery is added automatically. The patient pays by card before it goes out."
                                      : "Collection order: the patient pays in store."}
                    </p>
                    <button type="button" class="primary-button" id="send-invoice-btn">Order checked, send invoice</button>
                </div>`;
        }
        return `
            <h3 class="section-title">Invoice</h3>
            <div class="detail-box">
                <span>Prescription ${euro(inv.medicines_cents)}${inv.delivery_cents ? ` + delivery ${euro(inv.delivery_cents)}` : ""}</span>
                <strong>Total ${euro(inv.total_cents)} · ${escapeHTML(paymentLabel(order))}</strong>
                ${order.stripe_payment_intent ? `<span style="margin-top:6px">Stripe: ${escapeHTML(order.stripe_payment_intent)}</span>` : ""}
                ${order.payment_status === "pay_in_store"
                    ? `<button type="button" class="secondary-button" id="paid-in-store-btn" style="margin-top:10px">Paid at counter, mark collected</button>` : ""}
                ${order.payment_status === "paid" && order.fulfilment === "delivery" && order.status !== "delivered"
                    ? `<button type="button" class="primary-button" id="delivered-btn" style="margin-top:10px">Delivered to patient</button>` : ""}
            </div>`;
    }

    async function postJSON(url, body) {
        const res = await fetch(url, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body || {})
        });
        const result = await res.json();
        if (!res.ok || !result.ok) throw new Error(result.error || "Something went wrong.");
        return result;
    }

    function attachInvoice(order) {
        const feedback = document.getElementById("action-feedback");
        const sendButton = document.getElementById("send-invoice-btn");
        const paidButton = document.getElementById("paid-in-store-btn");
        const deliveredButton = document.getElementById("delivered-btn");

        if (deliveredButton) {
            deliveredButton.addEventListener("click", async () => {
                try {
                    await postJSON(`/payments/mark-delivered/${order.id}`);
                    window.location.hash = order.id;
                    window.location.reload();
                } catch (err) {
                    feedback.textContent = err.message;
                }
            });
        }

        if (sendButton) {
            sendButton.addEventListener("click", async () => {
                const amount = document.getElementById("medicines-euro").value;
                if (amount === "") {
                    feedback.textContent = "Enter the prescription charge first (0 is fine).";
                    return;
                }
                try {
                    await postJSON(`/payments/invoice/${order.id}`, { medicines_euro: amount });
                    window.location.hash = order.id;
                    window.location.reload();
                } catch (err) {
                    feedback.textContent = err.message;
                }
            });
        }
        if (paidButton) {
            paidButton.addEventListener("click", async () => {
                try {
                    await postJSON(`/payments/mark-paid/${order.id}`);
                    window.location.hash = order.id;
                    window.location.reload();
                } catch (err) {
                    feedback.textContent = err.message;
                }
            });
        }
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

        renewalButton.addEventListener("click", () => {
            const relatedRenewals = getRelatedRenewals(order.patient_id);

            feedback.textContent = relatedRenewals.some(
                renewal => renewal.status === "pending"
            )
                ? "A renewal request is already pending in the shared data. No new request was sent."
                : "Demo only: GP request has not been sent or saved.";
        });

        messageButton.addEventListener("click", () => {
            feedback.textContent =
                "Demo only: patient messaging is not connected yet.";
        });
    }

    // Renewal request buttons are informational for now.
    document.querySelectorAll(".renewal-demo-btn").forEach(button => {
        button.addEventListener("click", () => {
            button.textContent = "Request shown above";
        });
    });

    // Automatically select the oldest order.
    // (or the one in the URL after a reload, e.g. /pharmacy/#ord123)
    if (orders.length > 0) {
        const fromUrl = orders.find(o => o.id === window.location.hash.slice(1));
        const first = fromUrl || orders[0];
        selectedOrderId = first.id;
        renderOrders();
        renderDetails(first);
    }
}
