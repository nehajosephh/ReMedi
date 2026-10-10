"""ReMedi Assist: patients say what they need in their own words, AI ticks the boxes.

e.g. "I don't need the cholesterol meds" -> untick Atorvastatin
     "I want my painkillers"             -> tick the painkiller on their list

The AI only SUGGESTS. Our own code checks every answer:
  - it can only touch medicines that are on this patient's prescription list
  - it can never tick something that's expired, controlled or out of repeats
  - if it's unsure, it asks a question instead of guessing
  - the patient confirms, and a pharmacist checks every order anyway
If OpenRouter is down (or there's no key), a simple keyword matcher takes over.
"""
import json
import os
import re
from datetime import datetime
from pathlib import Path

import requests

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
LOG_FILE = Path(__file__).resolve().parent.parent / "data" / "ai_log.jsonl"

SYSTEM_PROMPT = """You help patients of an Irish community pharmacy choose which REPEAT medicines they need this month.

You get: the patient's message, their prescription list (id, name, directions) and which ids are ticked right now.
Patients often don't know drug names. They say things like "cholesterol meds", "my blood pressure tablets",
"the painkillers", "water tablet", "sugar tablets", "the blue inhaler", "thyroid one", "the usual".
Use your medical knowledge to work out which medicine on THEIR list they mean
(e.g. atorvastatin = cholesterol, metformin = diabetes/sugar, amlodipine and lisinopril = blood pressure,
salbutamol = blue reliever inhaler).

Rules:
1. Only use ids from the prescription list. Never invent medicines.
2. "tick" = ids to add, "untick" = ids to remove. Leave everything else as it is.
3. Read negatives carefully: "don't need", "no", "skip", "not this month", "without" mean UNTICK.
4. "same as last month" / "the usual" means tick the ones listed in last_month_ids.
5. If they ask for something NOT on their list (e.g. paracetamol, a new medicine), put their words in "not_on_list". Never tick anything for it.
6. If a phrase could mean more than one medicine on their list and you can't tell which (e.g. "my blood pressure tablet" when they have two), or the message is too vague ("I need my tablets"), set "action" to "clarify" and ask ONE short question. Don't guess.
7. Never give medical advice.
8. If the message has anything a pharmacist should know that ticking boxes can't handle
   (extra quantity, going on holiday, side effects, a question, ordering for someone else, a change in how they take it),
   write it as a short note to the pharmacist in "pharmacist_note", in the patient's voice. Otherwise leave it "".

Reply with JSON only:
{"action": "update" or "clarify",
 "tick": ["rx1"], "untick": ["rx4"],
 "matches": [{"said": "cholesterol meds", "id": "rx1"}],
 "not_on_list": [],
 "question": "",
 "pharmacist_note": "",
 "explanation": "one short plain-English sentence for the patient"}
"""


# ---------------- the AI call ----------------

def ask_openrouter(message, meds, ticked_ids, last_month_ids):
    key = os.getenv("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError("No OPENROUTER_API_KEY in .env")
    model = os.getenv("OPENROUTER_MODEL", "anthropic/claude-haiku-5.5")
    payload = {
        "patient_message": message,
        "prescription_list": [{"id": m["id"], "name": f"{m['drug']} {m['strength']}",
                               "directions": m.get("directions", "")} for m in meds],
        "ticked_now": ticked_ids,
        "last_month_ids": last_month_ids,
    }
    response = requests.post(
        OPENROUTER_URL,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                 "X-Title": "ReMedi (HackUCD 2026)"},
        json={"model": model, "temperature": 0,
              "response_format": {"type": "json_object"},
              "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                           {"role": "user", "content": json.dumps(payload)}]},
        timeout=20,
    )
    response.raise_for_status()
    text = response.json()["choices"][0]["message"]["content"]
    return parse_json(text), model


def parse_json(text):
    """Models sometimes wrap JSON in ```json fences``` or add chatter. Pull the object out."""
    try:
        return json.loads(text)
    except (TypeError, json.JSONDecodeError):
        found = re.search(r"\{.*\}", text or "", re.S)
        if not found:
            raise ValueError("AI didn't reply with JSON")
        return json.loads(found.group(0))


# ---------------- backup if the AI is unavailable: keyword matching ----------------

# everyday words patients use -> words that appear in the drug names
EVERYDAY_NAMES = {
    "cholesterol": ["atorvastatin", "rosuvastatin", "simvastatin", "pravastatin"],
    "statin": ["atorvastatin", "rosuvastatin", "simvastatin", "pravastatin"],
    "blood pressure": ["amlodipine", "lisinopril", "ramipril", "losartan", "bisoprolol"],
    "heart": ["bisoprolol", "aspirin", "clopidogrel"],
    "diabetes": ["metformin", "gliclazide", "insulin"],
    "sugar": ["metformin", "gliclazide", "insulin"],
    "painkiller": ["paracetamol", "codeine", "oxycodone", "tramadol", "ibuprofen", "naproxen"],
    "pain": ["paracetamol", "codeine", "oxycodone", "tramadol", "ibuprofen", "naproxen"],
    "inhaler": ["salbutamol", "beclometasone", "seretide", "symbicort"],
    "asthma": ["salbutamol", "beclometasone"],
    "thyroid": ["levothyroxine"],
    "stomach": ["omeprazole", "lansoprazole", "esomeprazole"],
    "heartburn": ["omeprazole", "lansoprazole", "esomeprazole"],
    "water tablet": ["furosemide", "bendroflumethiazide"],
}
NEGATIVE = re.compile(r"\b(no|not|don'?t|dont|skip|without|except|stop|leave out)\b")
NOTE_WORDS = re.compile(r"\b(holiday|away|extra|two months|2 months|double|side effect|sick|dizzy|reaction|"
                        r"question|husband|wife|mum|dad|instead)\b|\?")
USUAL = re.compile(r"\b(same as last month|the usual|same again|usual)\b")


def keyword_fallback(message, meds, ticked_ids, last_month_ids):
    text = message.lower()
    note = message if NOTE_WORDS.search(text) else ""
    tick, untick, matches = [], [], []
    if USUAL.search(text):
        tick += [i for i in last_month_ids if i not in ticked_ids]
    # split "no inhaler but I want my painkillers" into parts so each part keeps its own "no"
    for part in re.split(r"\bbut\b|,|\band\b|\.", text):
        negative = bool(NEGATIVE.search(part))
        for m in meds:
            drug = m["drug"].lower()
            words = [drug, drug.split()[0]] + [w for w, drugs in EVERYDAY_NAMES.items()
                                               if any(d in drug for d in drugs)]
            said = next((w for w in words if w in part), None)
            if said:
                matches.append({"said": said, "id": m["id"]})
                (untick if negative else tick).append(m["id"])
    if not tick and not untick:
        if note:  # nothing to tick, but there's something for the pharmacist
            return {"action": "update", "tick": [], "untick": [], "matches": [], "not_on_list": [],
                    "question": "", "pharmacist_note": note, "explanation": ""}
        return {"action": "clarify", "tick": [], "untick": [], "matches": [], "not_on_list": [],
                "question": "Which of your medicines do you mean?",
                "explanation": "I couldn't match that to anything on your list."}
    return {"action": "update", "tick": tick, "untick": untick, "matches": matches,
            "not_on_list": [], "question": "", "pharmacist_note": note, "explanation": ""}


# ---------------- safety net: check everything the AI said ----------------

def check_answer(raw, meds):
    by_id = {m["id"]: m for m in meds}
    result = {"action": "clarify" if raw.get("action") == "clarify" else "update",
              "tick": [], "untick": [], "blocked": [], "ignored": [],
              "not_on_list": [str(x) for x in raw.get("not_on_list") or [] if str(x).strip()],
              "question": (raw.get("question") or "").strip(),
              "explanation": (raw.get("explanation") or "").strip()[:200],
              "pharmacist_note": str(raw.get("pharmacist_note") or "").strip()[:300],
              "matches": [m for m in raw.get("matches") or [] if isinstance(m, dict) and m.get("id") in by_id]}
    for rx_id in raw.get("tick") or []:
        if rx_id not in by_id:
            result["ignored"].append(str(rx_id))          # AI made up an id
        elif not by_id[rx_id]["can_order"]:
            result["blocked"].append(rx_id)               # expired / controlled / no repeats
        elif rx_id not in result["tick"]:
            result["tick"].append(rx_id)
    for rx_id in raw.get("untick") or []:
        if rx_id in by_id and rx_id not in result["untick"] and rx_id not in result["tick"]:
            result["untick"].append(rx_id)
        elif rx_id not in by_id:
            result["ignored"].append(str(rx_id))
    if result["action"] == "clarify" and not result["question"]:
        result["question"] = "Which of your medicines do you mean?"
    return result


def understand_request(message, meds, ticked_ids, last_month_ids):
    """Main entry point used by routes/patient.py."""
    message = (message or "").strip()
    if not message:
        return {"ok": False, "error": "Type what you need first."}
    if len(message) > 300:
        return {"ok": False, "error": "Keep it to a sentence or two."}

    source, model, problem = "ai", None, None
    try:
        raw, model = ask_openrouter(message, meds, ticked_ids, last_month_ids)
    except Exception as e:  # no key, no wifi, bad JSON, rate limit...
        problem = str(e)[:150]
        source = "keywords"
        raw = keyword_fallback(message, meds, ticked_ids, last_month_ids)

    result = check_answer(raw, meds)
    result.update({"ok": True, "source": source, "model": model, "fallback_reason": problem})
    log(message, result)
    return result


def log(message, result):
    """Keep every request so we can show judges real examples, including mistakes."""
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps({"time": datetime.now().isoformat(timespec="seconds"),
                                "message": message, "result": result}, ensure_ascii=False) + "\n")
    except OSError:
        pass
