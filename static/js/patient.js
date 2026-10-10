// Patient medication list: selected count, highlight, delivery toggle, "are you sure?" check.
const form = document.getElementById("order-form");

function updateCount() {
  const boxes = form.querySelectorAll('input[name="items"]');
  const ticked = form.querySelectorAll('input[name="items"]:checked');
  document.getElementById("count").textContent = `${ticked.length} of ${boxes.length} selected`;
  boxes.forEach(b => b.closest(".med").classList.toggle("on", b.checked));
  document.getElementById("review-btn").disabled = ticked.length === 0;
}

form.querySelectorAll('input[name="items"]').forEach(b => b.addEventListener("change", updateCount));
updateCount();

// Delivery tile switches between home delivery and collection
document.getElementById("delivery-tile").addEventListener("click", () => {
  const input = document.getElementById("delivery");
  input.value = input.value === "home" ? "collect" : "home";
  document.getElementById("delivery-label").textContent = input.value === "home" ? "To home" : "Collect in store";
});

// If they unticked an important medicine they usually get, double check
form.addEventListener("submit", (e) => {
  const missing = [...form.querySelectorAll('input[name="items"][data-important="yes"]:not(:checked)')]
    .map(b => b.dataset.name);
  if (missing.length && !confirm(`You usually get ${missing.join(", ")} every month. Are you sure you don't need it this time?`)) {
    e.preventDefault();
  }
});