
const orders = {

    mary: {
        name: "Mary O'Sullivan",

        info: "Medical card. Delivery Thu 16 Oct, afternoon. GP: Glasnevin Family Practice, Glasnevin.",

        summary: 'Patient typed "same as last month but no inhaler". Matched to 3 items. Salbutamol removed. Nothing added.',

        medicines: [
            ["Atorvastatin 20mg", "28", "28", "3 of 6 left"],
            ["Metformin 500mg", "56", "56", "3 of 6 left"],
            ["Salbutamol 100mcg", "1", "Removed", "2 of 6 left"],
            ["Amlodipine 5mg", "28", "Wanted", "Expired 2 Oct"]
        ]
    },

    patrick: {
        name: "Patrick Murphy",

        info: "Collection requested. GP: Glasnevin Family Practice.",

        summary: "Patient requested the same medicines as last month. No changes identified in this fictional request.",

        medicines: [
            ["Demo Medicine A", "28", "28", "2 of 6 left"],
            ["Demo Medicine B", "30", "30", "3 of 6 left"]
        ]
    },

    brid: {
        name: "Bríd Gallagher",

        info: "Delivery requested for Friday. GP: Glasnevin Family Practice.",

        summary: "Patient requested a repeat. The prescription is on its final authorised repeat in this fictional record.",

        medicines: [
            ["Demo Medicine C", "28", "28", "Last repeat"]
        ]
    },

    sean: {
        name: "Seán O'Connor",

        info: "Delivery requested for Thursday. GP: Glasnevin Family Practice.",

        summary: "This fictional request was submitted earlier than the previous schedule. Pharmacist review required.",

        medicines: [
            ["Demo Medicine D", "28", "28", "Review required"]
        ]
    }
};


// Currently selected patient
let selectedOrder = "mary";


// SWITCH BETWEEN PATIENT ORDERS
document.querySelectorAll(".order-item").forEach(button => {

    button.addEventListener("click", () => {

        selectedOrder = button.dataset.order;

        const order = orders[selectedOrder];

        // Update selected appearance
        document.querySelectorAll(".order-item").forEach(item => {
            item.classList.remove("selected");
        });

        button.classList.add("selected");

        // Update patient information
        document.getElementById("patient-name").textContent =
            order.name;

        document.getElementById("patient-info").textContent =
            order.info;

        document.getElementById("ai-text").textContent =
            order.summary;

        // Update medicine table
        const tableBody =
            document.getElementById("medicine-table-body");

        tableBody.innerHTML = "";

        order.medicines.forEach(medicine => {

            const row = document.createElement("tr");

            medicine.forEach(value => {

                const cell = document.createElement("td");

                cell.textContent = value;

                if (
                    value === "Removed" ||
                    value === "Wanted" ||
                    value.startsWith("Expired")
                ) {
                    cell.classList.add("warning-text");
                }

                row.appendChild(cell);
            });

            tableBody.appendChild(row);
        });

        // Clear previous action message
        document.getElementById("action-feedback").textContent = "";

    });
});


// ACTION BUTTONS
// Demo only: no backend changes or messages are sent.

document.getElementById("approve-btn").addEventListener("click", () => {

    document.getElementById("action-feedback").textContent =
        "Demo: approval selected for " +
        orders[selectedOrder].name +
        ". No order has been changed.";

});


document.getElementById("renewal-btn").addEventListener("click", () => {

    document.getElementById("action-feedback").textContent =
        "Demo: renewal request selected for " +
        orders[selectedOrder].name +
        ". Nothing has been sent to a GP.";

});


document.getElementById("message-btn").addEventListener("click", () => {

    document.getElementById("action-feedback").textContent =
        "Demo: messaging selected for " +
        orders[selectedOrder].name +
        ". No message has been sent.";

});
