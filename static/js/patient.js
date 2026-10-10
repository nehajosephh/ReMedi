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


// ---------------- AI search bar ----------------
// Sends what the patient typed to /patient/assist. The server asks OpenRouter which boxes
// to tick or untick, checks the answer, and we show the change for the patient to confirm.
const aiInput = document.getElementById("ai-message");
const aiButton = document.getElementById("ai-go");
const aiBox = document.getElementById("ai-result");
const reviewButton = document.getElementById("review-btn");
let undoState = null;

function medName(id) {
  const card = form.querySelector(`.med[data-id="${id}"] strong`);
  return card ? card.textContent.trim() : id;
}

function escapeText(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

function setTicked(id, on) {
  const box = form.querySelector(`input[name="items"][value="${id}"]`);
  if (box) box.checked = on;
}

async function askAI() {
  const message = aiInput.value.trim();
  if (!message) { aiInput.focus(); return; }
  const ticked = [...form.querySelectorAll('input[name="items"]:checked')].map(b => b.value);

  aiButton.disabled = true;
  aiButton.textContent = "Reading your message…";
  try {
    const res = await fetch("/patient/assist", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, ticked }),
    });
    const result = await res.json();
    if (!res.ok) throw new Error(result.error || "Something went wrong.");
    showResult(result, ticked, message);
  } catch (err) {
    aiBox.hidden = false;
    aiBox.className = "ai-result bad";
    aiBox.textContent = err.message + " You can still tick the boxes yourself.";
  }
  aiButton.disabled = false;
  aiButton.textContent = "Update my list";
}

function showResult(r, tickedBefore, message) {
  form.querySelectorAll(".med.changed").forEach(c => c.classList.remove("changed"));
  aiBox.hidden = false;

  if (r.action === "clarify") {
    aiBox.className = "ai-result ask";
    aiBox.innerHTML = `<strong>Quick question</strong><div>${escapeText(r.question)}</div>
      <div class="small">Nothing has been changed.</div>`;
    return;
  }

  undoState = tickedBefore;
  r.tick.forEach(id => setTicked(id, true));
  r.untick.forEach(id => setTicked(id, false));
  [...r.tick, ...r.untick].forEach(id =>
    form.querySelector(`.med[data-id="${id}"]`)?.classList.add("changed"));
  updateCount();

  const lines = [];
  if (r.tick.length) lines.push(`Ticked: ${r.tick.map(medName).join(", ")}`);
  if (r.untick.length) lines.push(`Unticked: ${r.untick.map(medName).join(", ")}`);
  if (!r.tick.length && !r.untick.length) lines.push("No changes needed, your list already matches.");
  if (r.blocked.length) lines.push(`<span class="warn">${r.blocked.map(medName).join(", ")} can't be ordered right now. Tap "Ask my GP" on it.</span>`);
  if (r.not_on_list.length) lines.push(`<span class="warn">${escapeText(r.not_on_list.join(", "))} isn't on your prescription, so I can't add it. The pharmacy can help in store.</span>`);

  aiBox.className = "ai-result";
  aiBox.innerHTML = `<strong>I've updated your list</strong>
    <div>${lines.join("<br>")}</div>
    ${r.explanation ? `<div class="small">${escapeText(r.explanation)}</div>` : ""}
    <div class="ai-actions"><button type="button" class="btn btn-primary" id="ai-ok">Looks right</button>
      <button type="button" class="btn btn-outline" id="ai-undo">Undo</button></div>
    <div class="small">${r.source === "ai" ? "Suggested by AI" : "Matched by keywords (AI offline)"}. Highlighted boxes changed. It can make mistakes, so check them.</div>`;

  // Nothing is sent until the patient confirms
  reviewButton.disabled = true;
  document.getElementById("ai-message-sent").value = message;
  document.getElementById("ai-ok").onclick = () => {
    form.querySelectorAll(".med.changed").forEach(c => c.classList.remove("changed"));
    aiBox.hidden = true;
    updateCount();
  };
  document.getElementById("ai-undo").onclick = () => {
    form.querySelectorAll('input[name="items"]').forEach(b => { b.checked = undoState.includes(b.value); });
    form.querySelectorAll(".med.changed").forEach(c => c.classList.remove("changed"));
    document.getElementById("ai-message-sent").value = "";
    aiBox.hidden = true;
    updateCount();
  };
}

aiButton.addEventListener("click", askAI);
aiInput.addEventListener("keydown", e => { if (e.key === "Enter") { e.preventDefault(); askAI(); } });

// Voice input (works in Chrome and Edge)
const Speech = window.SpeechRecognition || window.webkitSpeechRecognition;
const micButton = document.getElementById("mic-btn");
if (Speech) {
  const listener = new Speech();
  listener.lang = "en-IE";
  listener.onresult = e => { aiInput.value = e.results[0][0].transcript; askAI(); };
  listener.onend = () => micButton.classList.remove("listening");
  micButton.addEventListener("click", () => { micButton.classList.add("listening"); listener.start(); });
} else {
  micButton.hidden = true;
}