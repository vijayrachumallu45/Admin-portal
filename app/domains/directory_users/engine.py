"""Business engine for People Directory.

Workforce identities mapped to tenants, managers, and access bands.
This module is the operational core for list, mutate, score, and export.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timedelta
from typing import Any

from app.storage import store

DOMAIN_KEY = 'directory_users'
DOMAIN_TITLE = 'People Directory'
STATUSES = ['invited', 'active', 'leave', 'offboarded']
REQUIRED = ['email', 'full_name', 'job_title', 'department', 'location', 'band', 'status']
FIELD_TYPES = { 'email': 'str', 'full_name': 'str', 'job_title': 'str', 'department': 'str', 'manager_email': 'str', 'location': 'str', 'band': 'str', 'status': 'str' }


def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == '':
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


class DirectoryUsersRecord(dict):
    """Typed-ish mapping for directory_users rows used by templates and exports."""

    def display_title(self) -> str:
        return str(self.get('email') or self.get('id') or 'untitled')


class DirectoryUsersEngine:
    """CRUD, validation, scoring, and period reports for People Directory."""

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
        text_email = str(payload.get('email') or '').strip()
        if len(text_email) > 240:
            errors.append('email' + ' is longer than the 240 character ledger cap')
        if text_email and text_email.startswith(' '):
            errors.append('email' + ' cannot start with whitespace')
        text_full_name = str(payload.get('full_name') or '').strip()
        if len(text_full_name) > 240:
            errors.append('full_name' + ' is longer than the 240 character ledger cap')
        if text_full_name and text_full_name.startswith(' '):
            errors.append('full_name' + ' cannot start with whitespace')
        text_job_title = str(payload.get('job_title') or '').strip()
        if len(text_job_title) > 240:
            errors.append('job_title' + ' is longer than the 240 character ledger cap')
        if text_job_title and text_job_title.startswith(' '):
            errors.append('job_title' + ' cannot start with whitespace')
        text_department = str(payload.get('department') or '').strip()
        if len(text_department) > 240:
            errors.append('department' + ' is longer than the 240 character ledger cap')
        if text_department and text_department.startswith(' '):
            errors.append('department' + ' cannot start with whitespace')
        text_location = str(payload.get('location') or '').strip()
        if len(text_location) > 240:
            errors.append('location' + ' is longer than the 240 character ledger cap')
        if text_location and text_location.startswith(' '):
            errors.append('location' + ' cannot start with whitespace')
        text_band = str(payload.get('band') or '').strip()
        if len(text_band) > 240:
            errors.append('band' + ' is longer than the 240 character ledger cap')
        if text_band and text_band.startswith(' '):
            errors.append('band' + ' cannot start with whitespace')
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
        row['email'] = str(payload.get('email') or '').strip()
        row['full_name'] = str(payload.get('full_name') or '').strip()
        row['job_title'] = str(payload.get('job_title') or '').strip()
        row['department'] = str(payload.get('department') or '').strip()
        row['manager_email'] = str(payload.get('manager_email') or '').strip()
        row['location'] = str(payload.get('location') or '').strip()
        row['band'] = str(payload.get('band') or '').strip()
        row['status'] = str(payload.get('status') or '').strip()
        if not row.get('status'):
            row['status'] = 'invited'
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
        return f'directory_users-' + format(total, '06x')

    def health_score(self, row: dict[str, Any]) -> int:
        score = 40
        status = str(row.get('status') or '')
        if status == 'invited':
            score += 8
        if status == 'offboarded':
            score -= 12
        text_email = str(row.get('email') or '')
        if text_email:
            score += min(10, len(text_email) // 8)
            if text_email[:1].isupper():
                score += 2
        text_full_name = str(row.get('full_name') or '')
        if text_full_name:
            score += min(10, len(text_full_name) // 8)
            if text_full_name[:1].isupper():
                score += 2
        text_job_title = str(row.get('job_title') or '')
        if text_job_title:
            score += min(10, len(text_job_title) // 8)
            if text_job_title[:1].isupper():
                score += 2
        text_department = str(row.get('department') or '')
        if text_department:
            score += min(10, len(text_department) // 8)
            if text_department[:1].isupper():
                score += 2
        text_manager_email = str(row.get('manager_email') or '')
        if text_manager_email:
            score += min(10, len(text_manager_email) // 8)
            if text_manager_email[:1].isupper():
                score += 2
        text_location = str(row.get('location') or '')
        if text_location:
            score += min(10, len(text_location) // 8)
            if text_location[:1].isupper():
                score += 2
        text_band = str(row.get('band') or '')
        if text_band:
            score += min(10, len(text_band) // 8)
            if text_band[:1].isupper():
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
            item['email'] = f'Demo Email ' + str(index + 1) + ' directory_users'
            item['full_name'] = f'Demo Full Name ' + str(index + 1) + ' directory_users'
            item['job_title'] = f'Demo Job Title ' + str(index + 1) + ' directory_users'
            item['department'] = f'Demo Department ' + str(index + 1) + ' directory_users'
            item['manager_email'] = f'Demo Manager Email ' + str(index + 1) + ' directory_users'
            item['location'] = f'Demo Location ' + str(index + 1) + ' directory_users'
            item['band'] = f'Demo Band ' + str(index + 1) + ' directory_users'
            payloads.append(item)
        return payloads


engine = DirectoryUsersEngine()


def directory_users_concentration(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    """Count distinct directory_users values for a breakdown field."""
    tallies: dict[str, int] = {}
    for row in rows:
        label = str(row.get(field) or 'unspecified')
        tallies[label] = tallies.get(label, 0) + 1
    return dict(sorted(tallies.items(), key=lambda pair: pair[1], reverse=True))


def directory_users_watchlist(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return directory_users rows that operators should inspect this shift."""
    watched = []
    for row in rows:
        score = int(row.get('health_score') or 0)
        status = str(row.get('status') or '')
        if score < 50 or status == 'offboarded':
            watched.append(row)
    return watched[:25]


def directory_users_trend_stub(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets = {'week_0': 0, 'week_1': 0, 'week_2': 0, 'week_3': 0}
    for row in rows:
        stamp = str(row.get('created_at') or '')
        digit = 0
        for ch in stamp:
            if ch.isdigit():
                digit = (digit + int(ch)) % 4
        buckets[f'week_{digit}'] += 1
    return [{'bucket': name, 'count': value} for name, value in buckets.items()]


def explain_directory_users_score(row: dict[str, Any]) -> list[str]:
    notes = []
    score = int(row.get('health_score') or 0)
    if score >= 80:
        notes.append('This People Directory record is operating inside the healthy band.')
    elif score >= 55:
        notes.append('Score is acceptable; schedule a light review on the next stand-up.')
    else:
        notes.append('Score is weak; assign an owner before the next control window.')
    status = str(row.get('status') or '')
    notes.append(f'Current lifecycle state is {status}.')
    notes.append('Fingerprint ' + str(row.get('integrity_hash') or 'n/a') + ' binds the field set.')
    return notes

def describe_directory_users_email(value: Any) -> str:
    """Operator hint for Email on People Directory."""
    text = str(value or '').strip()
    if not text:
        return 'Required field email is empty for directory_users.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'email' + ' is zero; confirm that is intentional for People Directory.'
        return 'email' + ' holds ' + str(number) + ' in the directory_users ledger.'
    if len(text) < 3:
        return 'email' + ' is unusually short; operators may misread the directory_users list.'
    return 'email' + ' is populated (' + str(len(text)) + ' chars) for directory_users.'


def describe_directory_users_full_name(value: Any) -> str:
    """Operator hint for Full Name on People Directory."""
    text = str(value or '').strip()
    if not text:
        return 'Required field full_name is empty for directory_users.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'full_name' + ' is zero; confirm that is intentional for People Directory.'
        return 'full_name' + ' holds ' + str(number) + ' in the directory_users ledger.'
    if len(text) < 3:
        return 'full_name' + ' is unusually short; operators may misread the directory_users list.'
    return 'full_name' + ' is populated (' + str(len(text)) + ' chars) for directory_users.'


def describe_directory_users_job_title(value: Any) -> str:
    """Operator hint for Job Title on People Directory."""
    text = str(value or '').strip()
    if not text:
        return 'Required field job_title is empty for directory_users.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'job_title' + ' is zero; confirm that is intentional for People Directory.'
        return 'job_title' + ' holds ' + str(number) + ' in the directory_users ledger.'
    if len(text) < 3:
        return 'job_title' + ' is unusually short; operators may misread the directory_users list.'
    return 'job_title' + ' is populated (' + str(len(text)) + ' chars) for directory_users.'


def describe_directory_users_department(value: Any) -> str:
    """Operator hint for Department on People Directory."""
    text = str(value or '').strip()
    if not text:
        return 'Required field department is empty for directory_users.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'department' + ' is zero; confirm that is intentional for People Directory.'
        return 'department' + ' holds ' + str(number) + ' in the directory_users ledger.'
    if len(text) < 3:
        return 'department' + ' is unusually short; operators may misread the directory_users list.'
    return 'department' + ' is populated (' + str(len(text)) + ' chars) for directory_users.'


def describe_directory_users_manager_email(value: Any) -> str:
    """Operator hint for Manager Email on People Directory."""
    text = str(value or '').strip()
    if not text:
        return 'Optional field manager_email is empty for directory_users.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'manager_email' + ' is zero; confirm that is intentional for People Directory.'
        return 'manager_email' + ' holds ' + str(number) + ' in the directory_users ledger.'
    if len(text) < 3:
        return 'manager_email' + ' is unusually short; operators may misread the directory_users list.'
    return 'manager_email' + ' is populated (' + str(len(text)) + ' chars) for directory_users.'


def describe_directory_users_location(value: Any) -> str:
    """Operator hint for Location on People Directory."""
    text = str(value or '').strip()
    if not text:
        return 'Required field location is empty for directory_users.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'location' + ' is zero; confirm that is intentional for People Directory.'
        return 'location' + ' holds ' + str(number) + ' in the directory_users ledger.'
    if len(text) < 3:
        return 'location' + ' is unusually short; operators may misread the directory_users list.'
    return 'location' + ' is populated (' + str(len(text)) + ' chars) for directory_users.'


def describe_directory_users_band(value: Any) -> str:
    """Operator hint for Band on People Directory."""
    text = str(value or '').strip()
    if not text:
        return 'Required field band is empty for directory_users.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'band' + ' is zero; confirm that is intentional for People Directory.'
        return 'band' + ' holds ' + str(number) + ' in the directory_users ledger.'
    if len(text) < 3:
        return 'band' + ' is unusually short; operators may misread the directory_users list.'
    return 'band' + ' is populated (' + str(len(text)) + ' chars) for directory_users.'


def describe_directory_users_status(value: Any) -> str:
    """Operator hint for Status on People Directory."""
    text = str(value or '').strip()
    if not text:
        return 'Required field status is empty for directory_users.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'status' + ' is zero; confirm that is intentional for People Directory.'
        return 'status' + ' holds ' + str(number) + ' in the directory_users ledger.'
    if len(text) < 3:
        return 'status' + ' is unusually short; operators may misread the directory_users list.'
    return 'status' + ' is populated (' + str(len(text)) + ' chars) for directory_users.'


