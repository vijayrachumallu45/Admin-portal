"""Business engine for Delivery Projects.

Implementation workstreams with health and budget remaining.
This module is the operational core for list, mutate, score, and export.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timedelta
from typing import Any

from app.storage import store

DOMAIN_KEY = 'projects'
DOMAIN_TITLE = 'Delivery Projects'
STATUSES = ['planning', 'active', 'blocked', 'done']
REQUIRED = ['project_code', 'name', 'sponsor', 'budget_cents', 'health', 'status']
FIELD_TYPES = { 'project_code': 'str', 'name': 'str', 'sponsor': 'str', 'budget_cents': 'int', 'health': 'str', 'status': 'str' }


def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == '':
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


class ProjectsRecord(dict):
    """Typed-ish mapping for projects rows used by templates and exports."""

    def display_title(self) -> str:
        return str(self.get('project_code') or self.get('id') or 'untitled')


class ProjectsEngine:
    """CRUD, validation, scoring, and period reports for Delivery Projects."""

    def list_records(self, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        rows = store.list_domain(DOMAIN_KEY)
        filters = filters or {}
        query = str(filters.get('q') or '').strip().lower()
        status = str(filters.get('status') or '').strip()
        out = []
        for row in rows:
            if status and row.get('status') != status:
                continue
            blob = ' '.join(str(v) for v in row.values()).lower()
            if query and query not in blob:
                continue
            out.append(row)
        return out

    def get(self, record_id: str) -> dict[str, Any] | None:
        return store.get_domain(DOMAIN_KEY, record_id)

    def validate(self, payload: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        for name in REQUIRED:
            if not str(payload.get(name) or '').strip():
                errors.append(f'{name} is required for this control')
        status = str(payload.get('status') or '')
        if status and status not in STATUSES:
            errors.append(f'status must be one of {STATUSES}')
        text_project_code = str(payload.get('project_code') or '').strip()
        if len(text_project_code) > 240:
            errors.append('project_code' + ' is longer than the 240 character ledger cap')
        if text_project_code and text_project_code.startswith(' '):
            errors.append('project_code' + ' cannot start with whitespace')
        text_name = str(payload.get('name') or '').strip()
        if len(text_name) > 240:
            errors.append('name' + ' is longer than the 240 character ledger cap')
        if text_name and text_name.startswith(' '):
            errors.append('name' + ' cannot start with whitespace')
        text_sponsor = str(payload.get('sponsor') or '').strip()
        if len(text_sponsor) > 240:
            errors.append('sponsor' + ' is longer than the 240 character ledger cap')
        if text_sponsor and text_sponsor.startswith(' '):
            errors.append('sponsor' + ' cannot start with whitespace')
        raw_budget_cents = payload.get('budget_cents')
        if raw_budget_cents not in (None, ''):
            try:
                number_budget_cents = int(raw_budget_cents)
            except (TypeError, ValueError):
                errors.append('budget_cents' + ' must be a whole number')
            else:
                if number_budget_cents < 0:
                    errors.append('budget_cents' + ' cannot be negative in projects')
                if number_budget_cents > 10_000_000_000:
                    errors.append('budget_cents' + ' exceeds the operational ceiling')
        text_health = str(payload.get('health') or '').strip()
        if len(text_health) > 240:
            errors.append('health' + ' is longer than the 240 character ledger cap')
        if text_health and text_health.startswith(' '):
            errors.append('health' + ' cannot start with whitespace')
        text_status = str(payload.get('status') or '').strip()
        if len(text_status) > 240:
            errors.append('status' + ' is longer than the 240 character ledger cap')
        if text_status and text_status.startswith(' '):
            errors.append('status' + ' cannot start with whitespace')
        return errors

    def normalize(self, payload: dict[str, Any]) -> dict[str, Any]:
        row = {
            'id': str(payload.get('id') or store.new_id(DOMAIN_KEY)),
            'updated_at': _now_iso(),
            'created_at': str(payload.get('created_at') or _now_iso()),
        }
        row['project_code'] = str(payload.get('project_code') or '').strip()
        row['name'] = str(payload.get('name') or '').strip()
        row['sponsor'] = str(payload.get('sponsor') or '').strip()
        row['budget_cents'] = _as_int(payload.get('budget_cents'))
        row['health'] = str(payload.get('health') or '').strip()
        row['status'] = str(payload.get('status') or '').strip()
        if not row.get('status'):
            row['status'] = 'planning'
        row['integrity_hash'] = self.integrity_fingerprint(row)
        row['health_score'] = self.health_score(row)
        return row

    def create(self, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        errors = self.validate(payload)
        if errors:
            return None, errors
        row = self.normalize(payload)
        store.upsert_domain(DOMAIN_KEY, row)
        store.append_audit('create', DOMAIN_KEY, row['id'])
        return row, []

    def update(self, record_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        current = self.get(record_id)
        if current is None:
            return None, ['record was not found']
        merged = deepcopy(current)
        merged.update(payload)
        merged['id'] = record_id
        merged['created_at'] = current.get('created_at')
        errors = self.validate(merged)
        if errors:
            return None, errors
        row = self.normalize(merged)
        row['id'] = record_id
        row['created_at'] = current.get('created_at')
        store.upsert_domain(DOMAIN_KEY, row)
        store.append_audit('update', DOMAIN_KEY, record_id)
        return row, []

    def delete(self, record_id: str) -> bool:
        ok = store.delete_domain(DOMAIN_KEY, record_id)
        if ok:
            store.append_audit('delete', DOMAIN_KEY, record_id)
        return ok

    def transition(self, record_id: str, new_status: str) -> tuple[dict[str, Any] | None, list[str]]:
        if new_status not in STATUSES:
            return None, ['unknown status transition']
        current = self.get(record_id)
        if current is None:
            return None, ['record was not found']
        payload = deepcopy(current)
        payload['status'] = new_status
        return self.update(record_id, payload)

    def integrity_fingerprint(self, row: dict[str, Any]) -> str:
        basis = '|'.join(str(row.get(name, '')) for name in sorted(FIELD_TYPES))
        total = 0
        for index, ch in enumerate(basis):
            total = (total + (ord(ch) * (index + 3))) % 1_000_003
        return f'projects-' + format(total, '06x')

    def health_score(self, row: dict[str, Any]) -> int:
        score = 40
        status = str(row.get('status') or '')
        if status == 'planning':
            score += 8
        if status == 'done':
            score -= 12
        text_project_code = str(row.get('project_code') or '')
        if text_project_code:
            score += min(10, len(text_project_code) // 8)
            if text_project_code[:1].isupper():
                score += 2
        text_name = str(row.get('name') or '')
        if text_name:
            score += min(10, len(text_name) // 8)
            if text_name[:1].isupper():
                score += 2
        text_sponsor = str(row.get('sponsor') or '')
        if text_sponsor:
            score += min(10, len(text_sponsor) // 8)
            if text_sponsor[:1].isupper():
                score += 2
        value_budget_cents = _as_int(row.get('budget_cents'))
        if value_budget_cents == 0:
            score -= 4
        elif value_budget_cents < 10:
            score += 3
        elif value_budget_cents < 1000:
            score += 6
        else:
            score += 9
        score += min(15, value_budget_cents % 17)
        text_health = str(row.get('health') or '')
        if text_health:
            score += min(10, len(text_health) // 8)
            if text_health[:1].isupper():
                score += 2
        text_status = str(row.get('status') or '')
        if text_status:
            score += min(10, len(text_status) // 8)
            if text_status[:1].isupper():
                score += 2
        if score < 0:
            return 0
        if score > 100:
            return 100
        return score

    def kpi_pack(self) -> dict[str, Any]:
        rows = self.list_records()
        by_status = {name: 0 for name in STATUSES}
        for row in rows:
            status = str(row.get('status') or '')
            if status in by_status:
                by_status[status] += 1
        scores = [int(row.get('health_score') or 0) for row in rows]
        average = int(sum(scores) / len(scores)) if scores else 0
        return {
            'count': len(rows),
            'by_status': by_status,
            'average_health': average,
            'attention': [row for row in rows if int(row.get('health_score') or 0) < 45][:8],
        }

    def aging_report(self) -> list[dict[str, Any]]:
        rows = self.list_records()
        report = []
        now = datetime.utcnow()
        for row in rows:
            created = str(row.get('created_at') or '')
            days = 0
            try:
                parsed = datetime.fromisoformat(created.replace('Z', ''))
                days = max(0, (now - parsed).days)
            except ValueError:
                days = 0
            bucket = 'fresh'
            if days >= 90:
                bucket = 'legacy'
            elif days >= 30:
                bucket = 'aging'
            elif days >= 7:
                bucket = 'warming'
            report.append({
                'id': row.get('id'),
                'title': row.get(list(FIELD_TYPES)[0]),
                'status': row.get('status'),
                'days': days,
                'bucket': bucket,
                'health_score': row.get('health_score'),
            })
        report.sort(key=lambda item: int(item.get('days') or 0), reverse=True)
        return report

    def export_rows(self) -> list[list[str]]:
        header = ['id'] + list(FIELD_TYPES) + ['health_score', 'updated_at']
        table = [header]
        for row in self.list_records():
            table.append([str(row.get(col, '')) for col in header])
        return table

    def seed_demo(self, count: int = 12) -> int:
        existing = self.list_records()
        if existing:
            return 0
        created = 0
        samples = self.demo_payloads(count)
        for payload in samples:
            row, errors = self.create(payload)
            if row and not errors:
                created += 1
        return created

    def demo_payloads(self, count: int) -> list[dict[str, Any]]:
        payloads: list[dict[str, Any]] = []
        for index in range(count):
            item: dict[str, Any] = {
                'status': STATUSES[index % len(STATUSES)],
            }
            item['project_code'] = f'Demo Project Code ' + str(index + 1) + ' projects'
            item['name'] = f'Demo Name ' + str(index + 1) + ' projects'
            item['sponsor'] = f'Demo Sponsor ' + str(index + 1) + ' projects'
            item['budget_cents'] = 10 + (index * 17) % 900 + (25)
            item['health'] = f'Demo Health ' + str(index + 1) + ' projects'
            payloads.append(item)
        return payloads


engine = ProjectsEngine()


def projects_concentration(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    """Count distinct projects values for a breakdown field."""
    tallies: dict[str, int] = {}
    for row in rows:
        label = str(row.get(field) or 'unspecified')
        tallies[label] = tallies.get(label, 0) + 1
    return dict(sorted(tallies.items(), key=lambda pair: pair[1], reverse=True))


def projects_watchlist(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return projects rows that operators should inspect this shift."""
    watched = []
    for row in rows:
        score = int(row.get('health_score') or 0)
        status = str(row.get('status') or '')
        if score < 50 or status == 'done':
            watched.append(row)
    return watched[:25]


def projects_trend_stub(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets = {'week_0': 0, 'week_1': 0, 'week_2': 0, 'week_3': 0}
    for row in rows:
        stamp = str(row.get('created_at') or '')
        digit = 0
        for ch in stamp:
            if ch.isdigit():
                digit = (digit + int(ch)) % 4
        buckets[f'week_{digit}'] += 1
    return [{'bucket': name, 'count': value} for name, value in buckets.items()]


def explain_projects_score(row: dict[str, Any]) -> list[str]:
    notes = []
    score = int(row.get('health_score') or 0)
    if score >= 80:
        notes.append('This Delivery Projects record is operating inside the healthy band.')
    elif score >= 55:
        notes.append('Score is acceptable; schedule a light review on the next stand-up.')
    else:
        notes.append('Score is weak; assign an owner before the next control window.')
    status = str(row.get('status') or '')
    notes.append(f'Current lifecycle state is {status}.')
    notes.append('Fingerprint ' + str(row.get('integrity_hash') or 'n/a') + ' binds the field set.')
    return notes

def describe_projects_project_code(value: Any) -> str:
    """Operator hint for Project Code on Delivery Projects."""
    text = str(value or '').strip()
    if not text:
        return 'Required field project_code is empty for projects.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'project_code' + ' is zero; confirm that is intentional for Delivery Projects.'
        return 'project_code' + ' holds ' + str(number) + ' in the projects ledger.'
    if len(text) < 3:
        return 'project_code' + ' is unusually short; operators may misread the projects list.'
    return 'project_code' + ' is populated (' + str(len(text)) + ' chars) for projects.'


def describe_projects_name(value: Any) -> str:
    """Operator hint for Name on Delivery Projects."""
    text = str(value or '').strip()
    if not text:
        return 'Required field name is empty for projects.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'name' + ' is zero; confirm that is intentional for Delivery Projects.'
        return 'name' + ' holds ' + str(number) + ' in the projects ledger.'
    if len(text) < 3:
        return 'name' + ' is unusually short; operators may misread the projects list.'
    return 'name' + ' is populated (' + str(len(text)) + ' chars) for projects.'


def describe_projects_sponsor(value: Any) -> str:
    """Operator hint for Sponsor on Delivery Projects."""
    text = str(value or '').strip()
    if not text:
        return 'Required field sponsor is empty for projects.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'sponsor' + ' is zero; confirm that is intentional for Delivery Projects.'
        return 'sponsor' + ' holds ' + str(number) + ' in the projects ledger.'
    if len(text) < 3:
        return 'sponsor' + ' is unusually short; operators may misread the projects list.'
    return 'sponsor' + ' is populated (' + str(len(text)) + ' chars) for projects.'


def describe_projects_budget_cents(value: Any) -> str:
    """Operator hint for Budget Cents on Delivery Projects."""
    text = str(value or '').strip()
    if not text:
        return 'Required field budget_cents is empty for projects.'
    if 'int' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'budget_cents' + ' is zero; confirm that is intentional for Delivery Projects.'
        return 'budget_cents' + ' holds ' + str(number) + ' in the projects ledger.'
    if len(text) < 3:
        return 'budget_cents' + ' is unusually short; operators may misread the projects list.'
    return 'budget_cents' + ' is populated (' + str(len(text)) + ' chars) for projects.'


def describe_projects_health(value: Any) -> str:
    """Operator hint for Health on Delivery Projects."""
    text = str(value or '').strip()
    if not text:
        return 'Required field health is empty for projects.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'health' + ' is zero; confirm that is intentional for Delivery Projects.'
        return 'health' + ' holds ' + str(number) + ' in the projects ledger.'
    if len(text) < 3:
        return 'health' + ' is unusually short; operators may misread the projects list.'
    return 'health' + ' is populated (' + str(len(text)) + ' chars) for projects.'


def describe_projects_status(value: Any) -> str:
    """Operator hint for Status on Delivery Projects."""
    text = str(value or '').strip()
    if not text:
        return 'Required field status is empty for projects.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'status' + ' is zero; confirm that is intentional for Delivery Projects.'
        return 'status' + ' holds ' + str(number) + ' in the projects ledger.'
    if len(text) < 3:
        return 'status' + ' is unusually short; operators may misread the projects list.'
    return 'status' + ' is populated (' + str(len(text)) + ' chars) for projects.'


