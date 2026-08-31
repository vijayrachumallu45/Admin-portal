"""Session login, logout, and password hashing."""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable

from flask import flash, redirect, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from app.config import DEMO_EMAIL, DEMO_NAME, DEMO_PASSWORD
from app.storage import store


def bootstrap_demo_operator() -> None:
    if store.get_operator(DEMO_EMAIL) is None:
        store.upsert_operator(
            DEMO_EMAIL,
            DEMO_NAME,
            generate_password_hash(DEMO_PASSWORD),
            "director",
        )


def authenticate(email: str, password: str) -> dict[str, Any] | None:
    operator = store.get_operator(email.strip().lower())
    if operator is None:
        return None
    if not check_password_hash(operator["password_hash"], password):
        return None
    return operator


def login_operator(operator: dict[str, Any]) -> None:
    session.clear()
    session["email"] = operator["email"]
    session["name"] = operator["name"]
    session["role"] = operator["role"]


def logout_operator() -> None:
    session.clear()


def current_operator() -> dict[str, Any] | None:
    email = session.get("email")
    if not email:
        return None
    return {
        "email": email,
        "name": session.get("name") or email,
        "role": session.get("role") or "operator",
    }


def login_required(view: Callable) -> Callable:
    @wraps(view)
    def wrapped(*args: Any, **kwargs: Any):
        if current_operator() is None:
            flash("Sign in to open the control plane.", "error")
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped
