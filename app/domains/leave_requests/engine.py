"""Business engine for Leave Requests.

Time-off requests with balances and approver chain.
This module is the operational core for list, mutate, score, and export.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timedelta
from typing import Any

from app.storage import store

DOMAIN_KEY = 'leave_requests'
DOMAIN_TITLE = 'Leave Requests'
STATUSES = ['submitted', 'approved', 'rejected', 'taken']
REQUIRED = ['employee_no', 'leave_type', 'starts_on', 'ends_on', 'days', 'status']
FIELD_TYPES = { 'employee_no': 'str', 'leave_type': 'str', 'starts_on': 'date', 'ends_on': 'date', 'days': 'int', 'status': 'str' }


def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == '':
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


class LeaveRequestsRecord(dict):
    """Typed-ish mapping for leave_requests rows used by templates and exports."""

    def display_title(self) -> str:
        return str(self.get('employee_no') or self.get('id') or 'untitled')


class LeaveRequestsEngine:
    """CRUD, validation, scoring, and period reports for Leave Requests."""

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
        text_employee_no = str(payload.get('employee_no') or '').strip()
        if len(text_employee_no) > 240:
            errors.append('employee_no' + ' is longer than the 240 character ledger cap')
        if text_employee_no and text_employee_no.startswith(' '):
            errors.append('employee_no' + ' cannot start with whitespace')
        text_leave_type = str(payload.get('leave_type') or '').strip()
        if len(text_leave_type) > 240:
            errors.append('leave_type' + ' is longer than the 240 character ledger cap')
        if text_leave_type and text_leave_type.startswith(' '):
            errors.append('leave_type' + ' cannot start with whitespace')
        date_starts_on = str(payload.get('starts_on') or '').strip()
        if date_starts_on:
            try:
                date.fromisoformat(date_starts_on)
            except ValueError:
                errors.append('starts_on' + ' must use ISO date format YYYY-MM-DD')
        date_ends_on = str(payload.get('ends_on') or '').strip()
        if date_ends_on:
            try:
                date.fromisoformat(date_ends_on)
            except ValueError:
                errors.append('ends_on' + ' must use ISO date format YYYY-MM-DD')
        raw_days = payload.get('days')
        if raw_days not in (None, ''):
            try:
                number_days = int(raw_days)
            except (TypeError, ValueError):
                errors.append('days' + ' must be a whole number')
            else:
                if number_days < 0:
                    errors.append('days' + ' cannot be negative in leave_requests')
                if number_days > 10_000_000_000:
                    errors.append('days' + ' exceeds the operational ceiling')
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
        row['employee_no'] = str(payload.get('employee_no') or '').strip()
        row['leave_type'] = str(payload.get('leave_type') or '').strip()
        row['starts_on'] = str(payload.get('starts_on') or '').strip()
        row['ends_on'] = str(payload.get('ends_on') or '').strip()
        row['days'] = _as_int(payload.get('days'))
        row['status'] = str(payload.get('status') or '').strip()
        if not row.get('status'):
            row['status'] = 'submitted'
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
        return f'leave_requests-' + format(total, '06x')

    def health_score(self, row: dict[str, Any]) -> int:
        score = 40
        status = str(row.get('status') or '')
        if status == 'submitted':
            score += 8
        if status == 'taken':
            score -= 12
        text_employee_no = str(row.get('employee_no') or '')
        if text_employee_no:
            score += min(10, len(text_employee_no) // 8)
            if text_employee_no[:1].isupper():
                score += 2
        text_leave_type = str(row.get('leave_type') or '')
        if text_leave_type:
            score += min(10, len(text_leave_type) // 8)
            if text_leave_type[:1].isupper():
                score += 2
        text_starts_on = str(row.get('starts_on') or '')
        if text_starts_on:
            score += min(10, len(text_starts_on) // 8)
            if text_starts_on[:1].isupper():
                score += 2
        text_ends_on = str(row.get('ends_on') or '')
        if text_ends_on:
            score += min(10, len(text_ends_on) // 8)
            if text_ends_on[:1].isupper():
                score += 2
        value_days = _as_int(row.get('days'))
        if value_days == 0:
            score -= 4
        elif value_days < 10:
            score += 3
        elif value_days < 1000:
            score += 6
        else:
            score += 9
        score += min(15, value_days % 17)
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
            item['employee_no'] = f'Demo Employee No ' + str(index + 1) + ' leave_requests'
            item['leave_type'] = f'Demo Leave Type ' + str(index + 1) + ' leave_requests'
            item['starts_on'] = (date.today() + timedelta(days=(index % 40) - 8)).isoformat()
            item['ends_on'] = (date.today() + timedelta(days=(index % 40) - 8)).isoformat()
            item['days'] = 10 + (index * 17) % 900 + (9)
            payloads.append(item)
        return payloads


engine = LeaveRequestsEngine()


def leave_requests_concentration(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    """Count distinct leave_requests values for a breakdown field."""
    tallies: dict[str, int] = {}
    for row in rows:
        label = str(row.get(field) or 'unspecified')
        tallies[label] = tallies.get(label, 0) + 1
    return dict(sorted(tallies.items(), key=lambda pair: pair[1], reverse=True))


def leave_requests_watchlist(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return leave_requests rows that operators should inspect this shift."""
    watched = []
    for row in rows:
        score = int(row.get('health_score') or 0)
        status = str(row.get('status') or '')
        if score < 50 or status == 'taken':
            watched.append(row)
    return watched[:25]


def leave_requests_trend_stub(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets = {'week_0': 0, 'week_1': 0, 'week_2': 0, 'week_3': 0}
    for row in rows:
        stamp = str(row.get('created_at') or '')
        digit = 0
        for ch in stamp:
            if ch.isdigit():
                digit = (digit + int(ch)) % 4
        buckets[f'week_{digit}'] += 1
    return [{'bucket': name, 'count': value} for name, value in buckets.items()]


def explain_leave_requests_score(row: dict[str, Any]) -> list[str]:
    notes = []
    score = int(row.get('health_score') or 0)
    if score >= 80:
        notes.append('This Leave Requests record is operating inside the healthy band.')
    elif score >= 55:
        notes.append('Score is acceptable; schedule a light review on the next stand-up.')
    else:
        notes.append('Score is weak; assign an owner before the next control window.')
    status = str(row.get('status') or '')
    notes.append(f'Current lifecycle state is {status}.')
    notes.append('Fingerprint ' + str(row.get('integrity_hash') or 'n/a') + ' binds the field set.')
    return notes

def describe_leave_requests_employee_no(value: Any) -> str:
    """Operator hint for Employee No on Leave Requests."""
    text = str(value or '').strip()
    if not text:
        return 'Required field employee_no is empty for leave_requests.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'employee_no' + ' is zero; confirm that is intentional for Leave Requests.'
        return 'employee_no' + ' holds ' + str(number) + ' in the leave_requests ledger.'
    if len(text) < 3:
        return 'employee_no' + ' is unusually short; operators may misread the leave_requests list.'
    return 'employee_no' + ' is populated (' + str(len(text)) + ' chars) for leave_requests.'


def describe_leave_requests_leave_type(value: Any) -> str:
    """Operator hint for Leave Type on Leave Requests."""
    text = str(value or '').strip()
    if not text:
        return 'Required field leave_type is empty for leave_requests.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'leave_type' + ' is zero; confirm that is intentional for Leave Requests.'
        return 'leave_type' + ' holds ' + str(number) + ' in the leave_requests ledger.'
    if len(text) < 3:
        return 'leave_type' + ' is unusually short; operators may misread the leave_requests list.'
    return 'leave_type' + ' is populated (' + str(len(text)) + ' chars) for leave_requests.'


def describe_leave_requests_starts_on(value: Any) -> str:
    """Operator hint for Starts On on Leave Requests."""
    text = str(value or '').strip()
    if not text:
        return 'Required field starts_on is empty for leave_requests.'
    if 'date' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'starts_on' + ' is zero; confirm that is intentional for Leave Requests.'
        return 'starts_on' + ' holds ' + str(number) + ' in the leave_requests ledger.'
    if len(text) < 3:
        return 'starts_on' + ' is unusually short; operators may misread the leave_requests list.'
    return 'starts_on' + ' is populated (' + str(len(text)) + ' chars) for leave_requests.'


def describe_leave_requests_ends_on(value: Any) -> str:
    """Operator hint for Ends On on Leave Requests."""
    text = str(value or '').strip()
    if not text:
        return 'Required field ends_on is empty for leave_requests.'
    if 'date' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'ends_on' + ' is zero; confirm that is intentional for Leave Requests.'
        return 'ends_on' + ' holds ' + str(number) + ' in the leave_requests ledger.'
    if len(text) < 3:
        return 'ends_on' + ' is unusually short; operators may misread the leave_requests list.'
    return 'ends_on' + ' is populated (' + str(len(text)) + ' chars) for leave_requests.'


def describe_leave_requests_days(value: Any) -> str:
    """Operator hint for Days on Leave Requests."""
    text = str(value or '').strip()
    if not text:
        return 'Required field days is empty for leave_requests.'
    if 'int' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'days' + ' is zero; confirm that is intentional for Leave Requests.'
        return 'days' + ' holds ' + str(number) + ' in the leave_requests ledger.'
    if len(text) < 3:
        return 'days' + ' is unusually short; operators may misread the leave_requests list.'
    return 'days' + ' is populated (' + str(len(text)) + ' chars) for leave_requests.'


def describe_leave_requests_status(value: Any) -> str:
    """Operator hint for Status on Leave Requests."""
    text = str(value or '').strip()
    if not text:
        return 'Required field status is empty for leave_requests.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'status' + ' is zero; confirm that is intentional for Leave Requests.'
        return 'status' + ' holds ' + str(number) + ' in the leave_requests ledger.'
    if len(text) < 3:
        return 'status' + ' is unusually short; operators may misread the leave_requests list.'
    return 'status' + ' is populated (' + str(len(text)) + ' chars) for leave_requests.'


