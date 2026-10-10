"""Prescription rules in plain code (no AI). Everyone can import these:
from services.prescription_rules import item_state, repeats_left, next_due_date
"""
from datetime import date, datetime


def today():
    return date.today()


def parse_date(text):
    return datetime.strptime(text[:10], "%Y-%m-%d").date()


def pretty_date(text):
    """'2026-10-02' -> '2 October'"""
    d = parse_date(text)
    return f"{d.day} {d.strftime('%B')}"


def repeats_left(rx):
    return max(rx["repeats_total"] - rx["repeats_used"], 0)


def item_state(rx):
    """Work out if a prescription line can be ordered.
    Returns (can_order, state, message). state is one of:
    ok, last_repeat, expired, no_repeats, controlled
    """
    if rx.get("controlled"):
        return False, "controlled", "Controlled drug. Needs a new prescription each time."
    if parse_date(rx["expiry"]) < today():
        return False, "expired", f"Prescription expired on {pretty_date(rx['expiry'])}"
    if repeats_left(rx) == 0:
        return False, "no_repeats", "No repeats left on this prescription"
    if repeats_left(rx) == 1:
        return True, "last_repeat", "Last repeat. Book a GP review."
    return True, "ok", ""


def next_due_date(prescriptions):
    """Earliest date any of these medicines runs out, based on when it was last dispensed."""
    dates = []
    for rx in prescriptions:
        if rx.get("last_dispensed"):
            runs_out = parse_date(rx["last_dispensed"]).toordinal() + rx["supply_days"]
            dates.append(date.fromordinal(runs_out))
    return min(dates) if dates else None