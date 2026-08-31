NexusOps Admin Portal
=====================

Private enterprise SaaS admin portal for a local operator control plane.
This repository is **not** open source, is **not** licensed under GPL, Apache,
or any OSI license, and is **not** a university paper.

The software is proprietary. All rights reserved. You may use this copy for
evaluation of the enclosed application only.

What it is
----------

A working Flask website with HTML and CSS for:

- Sign in / sign out
- Command-center dashboard
- Operator profile and workspace settings
- Dozens of operational ledgers (tenants, billing, inventory, HR, ITSM, CRM, and more)
- Create, edit, status transitions, delete, CSV export, and aging reports
- Local SQLite storage (no cloud API keys)

Supported language
------------------

Python 3.11+ with HTML, CSS, and a small amount of JavaScript.

Run
---

```text
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python tools/build_portal.py
python wsgi.py
```

Open http://127.0.0.1:5000

Demo operator (local only)
--------------------------

- Email: `admin@nexusops.local`
- Password: `NexusAdmin#2026`

These values seed an empty local database. They are not production secrets
and are not cloud API keys.

Measure production LOC
----------------------

```text
python measure.py
```

Tests
-----

```text
python -m pytest
```

Lockfile
--------

`requirements.lock` pins the install set used to run this tree.

Layout
------

- `app/` application factory, security, storage, domain packages
- `templates/` HTML (login, shell, dashboard, domain screens)
- `static/css` and `static/js` presentation
- `tests/` pytest coverage
- `var/` local database and session material (gitignored)

Out of scope
------------

Open-source relicensing, Apache HTTP Server, GPL, client-owned handover packs,
committed `.env` files, and third-party API keys.
