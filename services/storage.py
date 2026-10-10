"""Shared helpers for reading and writing data/data.json. Everyone imports from here."""
import json
import os
from functools import wraps

from flask import redirect, session, url_for

DATA_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "data.json")


def load_data():
    with open(DATA_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def find_by(items, key, value):
    """First item in a list where item[key] == value, or None."""
    return next((item for item in items if item.get(key) == value), None)


def login_required(role):
    """Use @login_required("patient") above a route to block anyone not logged in as that role."""
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if session.get("role") != role:
                return redirect(url_for("welcome"))
            return view(*args, **kwargs)
        return wrapped
    return decorator