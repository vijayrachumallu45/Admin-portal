"""NexusOps enterprise admin portal application factory."""

from __future__ import annotations

from flask import Flask, flash, redirect, render_template, request, session, url_for

from app.config import SECRET_FALLBACK, SESSION_COOKIE_NAME, secret_key
from app.domain_catalog import CATALOG
from app.security import (
    authenticate,
    bootstrap_demo_operator,
    current_operator,
    login_operator,
    login_required,
    logout_operator,
)
from app.storage import store


def create_app() -> Flask:
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.config["SECRET_KEY"] = secret_key() or SECRET_FALLBACK
    app.config["SESSION_COOKIE_NAME"] = SESSION_COOKIE_NAME
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

    bootstrap_demo_operator()
    register_domains(app)
    register_pages(app)
    return app


def register_domains(app: Flask) -> None:
    for item in CATALOG:
        key = item["key"]
        module = __import__(f"app.domains.{key}.routes", fromlist=["bp"])
        app.register_blueprint(module.bp)
        engine_mod = __import__(f"app.domains.{key}.engine", fromlist=["engine"])
        engine_mod.engine.seed_demo(10)


def register_pages(app: Flask) -> None:
    @app.context_processor
    def inject_globals():
        return {
            "operator": current_operator(),
            "catalog": CATALOG,
        }

    @app.get("/")
    def home():
        if current_operator():
            return redirect(url_for("dashboard"))
        return redirect(url_for("login"))

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if current_operator():
            return redirect(url_for("dashboard"))
        error = None
        if request.method == "POST":
            email = request.form.get("email", "")
            password = request.form.get("password", "")
            operator = authenticate(email, password)
            if operator:
                login_operator(operator)
                flash("Signed in to NexusOps.", "ok")
                return redirect(url_for("dashboard"))
            error = "Those credentials do not match a local operator."
        return render_template("login.html", error=error)

    @app.post("/logout")
    def logout():
        logout_operator()
        flash("Signed out.", "ok")
        return redirect(url_for("login"))

    @app.get("/dashboard")
    @login_required
    def dashboard():
        counts = store.count_domains()
        cards = []
        for item in CATALOG:
            cards.append(
                {
                    "title": item["title"],
                    "desc": item["desc"],
                    "nav": item["nav"],
                    "key": item["key"],
                    "count": counts.get(item["key"], 0),
                    "href": url_for(f"{item['key']}.list_{item['key']}"),
                }
            )
        return render_template(
            "dashboard.html",
            cards=cards,
            total_rows=sum(card["count"] for card in cards),
            audit=store.recent_audit(),
            session_email=session.get("email"),
        )

    @app.get("/search")
    @login_required
    def search():
        query = request.args.get("q", "").strip()
        results = []
        if query:
            for item in CATALOG:
                domain = item["key"]
                rows = store.list_domain(domain)
                for row in rows:
                    haystack = " ".join(str(value) for value in row.values()).lower()
                    if query.lower() in haystack:
                        results.append(
                            {
                                "domain": item["title"],
                                "key": domain,
                                "record_id": row.get("id", "unknown"),
                                "summary": " ".join(
                                    f"{key}={value}"
                                    for key, value in row.items()
                                    if key != "id" and value not in (None, "")
                                )[:140],
                            }
                        )
        return render_template(
            "search.html",
            query=query,
            results=results,
            total_results=len(results),
        )

    @app.get("/profile")
    @login_required
    def profile():
        return render_template("profile.html")

    @app.get("/settings")
    @login_required
    def settings():
        return render_template("settings.html")

    @app.get("/healthz")
    def healthz():
        return {"ok": True, "service": "nexusops-admin"}
