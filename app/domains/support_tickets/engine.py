"""Business engine for Support Queue.

Customer issues with severity, SLA clocks, and owners.
This module is the operational core for list, mutate, score, and export.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timedelta
from typing import Any

from app.storage import store

DOMAIN_KEY = 'support_tickets'
DOMAIN_TITLE = 'Support Queue'
STATUSES = ['new', 'open', 'pending', 'resolved', 'closed']
REQUIRED = ['ticket_no', 'subject', 'severity', 'requester', 'status']
FIELD_TYPES = { 'ticket_no': 'str', 'subject': 'str', 'severity': 'str', 'requester': 'str', 'assignee': 'str', 'status': 'str' }


def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == '':
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


class SupportTicketsRecord(dict):
    """Typed-ish mapping for support_tickets rows used by templates and exports."""

    def display_title(self) -> str:
        return str(self.get('ticket_no') or self.get('id') or 'untitled')


class SupportTicketsEngine:
    """CRUD, validation, scoring, and period reports for Support Queue."""

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
        text_ticket_no = str(payload.get('ticket_no') or '').strip()
        if len(text_ticket_no) > 240:
            errors.append('ticket_no' + ' is longer than the 240 character ledger cap')
        if text_ticket_no and text_ticket_no.startswith(' '):
            errors.append('ticket_no' + ' cannot start with whitespace')
        text_subject = str(payload.get('subject') or '').strip()
        if len(text_subject) > 240:
            errors.append('subject' + ' is longer than the 240 character ledger cap')
        if text_subject and text_subject.startswith(' '):
            errors.append('subject' + ' cannot start with whitespace')
        text_severity = str(payload.get('severity') or '').strip()
        if len(text_severity) > 240:
            errors.append('severity' + ' is longer than the 240 character ledger cap')
        if text_severity and text_severity.startswith(' '):
            errors.append('severity' + ' cannot start with whitespace')
        text_requester = str(payload.get('requester') or '').strip()
        if len(text_requester) > 240:
            errors.append('requester' + ' is longer than the 240 character ledger cap')
        if text_requester and text_requester.startswith(' '):
            errors.append('requester' + ' cannot start with whitespace')
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
        row['ticket_no'] = str(payload.get('ticket_no') or '').strip()
        row['subject'] = str(payload.get('subject') or '').strip()
        row['severity'] = str(payload.get('severity') or '').strip()
        row['requester'] = str(payload.get('requester') or '').strip()
        row['assignee'] = str(payload.get('assignee') or '').strip()
        row['status'] = str(payload.get('status') or '').strip()
        if not row.get('status'):
            row['status'] = 'new'
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
        return f'support_tickets-' + format(total, '06x')

    def health_score(self, row: dict[str, Any]) -> int:
        score = 40
        status = str(row.get('status') or '')
        if status == 'new':
            score += 8
        if status == 'closed':
            score -= 12
        text_ticket_no = str(row.get('ticket_no') or '')
        if text_ticket_no:
            score += min(10, len(text_ticket_no) // 8)
            if text_ticket_no[:1].isupper():
                score += 2
        text_subject = str(row.get('subject') or '')
        if text_subject:
            score += min(10, len(text_subject) // 8)
            if text_subject[:1].isupper():
                score += 2
        text_severity = str(row.get('severity') or '')
        if text_severity:
            score += min(10, len(text_severity) // 8)
            if text_severity[:1].isupper():
                score += 2
        text_requester = str(row.get('requester') or '')
        if text_requester:
            score += min(10, len(text_requester) // 8)
            if text_requester[:1].isupper():
                score += 2
        text_assignee = str(row.get('assignee') or '')
        if text_assignee:
            score += min(10, len(text_assignee) // 8)
            if text_assignee[:1].isupper():
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
            item['ticket_no'] = f'Demo Ticket No ' + str(index + 1) + ' support_tickets'
            item['subject'] = f'Demo Subject ' + str(index + 1) + ' support_tickets'
            item['severity'] = f'Demo Severity ' + str(index + 1) + ' support_tickets'
            item['requester'] = f'Demo Requester ' + str(index + 1) + ' support_tickets'
            item['assignee'] = f'Demo Assignee ' + str(index + 1) + ' support_tickets'
            payloads.append(item)
        return payloads


engine = SupportTicketsEngine()


def support_tickets_concentration(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    """Count distinct support_tickets values for a breakdown field."""
    tallies: dict[str, int] = {}
    for row in rows:
        label = str(row.get(field) or 'unspecified')
        tallies[label] = tallies.get(label, 0) + 1
    return dict(sorted(tallies.items(), key=lambda pair: pair[1], reverse=True))


def support_tickets_watchlist(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return support_tickets rows that operators should inspect this shift."""
    watched = []
    for row in rows:
        score = int(row.get('health_score') or 0)
        status = str(row.get('status') or '')
        if score < 50 or status == 'closed':
            watched.append(row)
    return watched[:25]


def support_tickets_trend_stub(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets = {'week_0': 0, 'week_1': 0, 'week_2': 0, 'week_3': 0}
    for row in rows:
        stamp = str(row.get('created_at') or '')
        digit = 0
        for ch in stamp:
            if ch.isdigit():
                digit = (digit + int(ch)) % 4
        buckets[f'week_{digit}'] += 1
    return [{'bucket': name, 'count': value} for name, value in buckets.items()]


def explain_support_tickets_score(row: dict[str, Any]) -> list[str]:
    notes = []
    score = int(row.get('health_score') or 0)
    if score >= 80:
        notes.append('This Support Queue record is operating inside the healthy band.')
    elif score >= 55:
        notes.append('Score is acceptable; schedule a light review on the next stand-up.')
    else:
        notes.append('Score is weak; assign an owner before the next control window.')
    status = str(row.get('status') or '')
    notes.append(f'Current lifecycle state is {status}.')
    notes.append('Fingerprint ' + str(row.get('integrity_hash') or 'n/a') + ' binds the field set.')
    return notes

def describe_support_tickets_ticket_no(value: Any) -> str:
    """Operator hint for Ticket No on Support Queue."""
    text = str(value or '').strip()
    if not text:
        return 'Required field ticket_no is empty for support_tickets.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'ticket_no' + ' is zero; confirm that is intentional for Support Queue.'
        return 'ticket_no' + ' holds ' + str(number) + ' in the support_tickets ledger.'
    if len(text) < 3:
        return 'ticket_no' + ' is unusually short; operators may misread the support_tickets list.'
    return 'ticket_no' + ' is populated (' + str(len(text)) + ' chars) for support_tickets.'


def describe_support_tickets_subject(value: Any) -> str:
    """Operator hint for Subject on Support Queue."""
    text = str(value or '').strip()
    if not text:
        return 'Required field subject is empty for support_tickets.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'subject' + ' is zero; confirm that is intentional for Support Queue.'
        return 'subject' + ' holds ' + str(number) + ' in the support_tickets ledger.'
    if len(text) < 3:
        return 'subject' + ' is unusually short; operators may misread the support_tickets list.'
    return 'subject' + ' is populated (' + str(len(text)) + ' chars) for support_tickets.'


def describe_support_tickets_severity(value: Any) -> str:
    """Operator hint for Severity on Support Queue."""
    text = str(value or '').strip()
    if not text:
        return 'Required field severity is empty for support_tickets.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'severity' + ' is zero; confirm that is intentional for Support Queue.'
        return 'severity' + ' holds ' + str(number) + ' in the support_tickets ledger.'
    if len(text) < 3:
        return 'severity' + ' is unusually short; operators may misread the support_tickets list.'
    return 'severity' + ' is populated (' + str(len(text)) + ' chars) for support_tickets.'


def describe_support_tickets_requester(value: Any) -> str:
    """Operator hint for Requester on Support Queue."""
    text = str(value or '').strip()
    if not text:
        return 'Required field requester is empty for support_tickets.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'requester' + ' is zero; confirm that is intentional for Support Queue.'
        return 'requester' + ' holds ' + str(number) + ' in the support_tickets ledger.'
    if len(text) < 3:
        return 'requester' + ' is unusually short; operators may misread the support_tickets list.'
    return 'requester' + ' is populated (' + str(len(text)) + ' chars) for support_tickets.'


def describe_support_tickets_assignee(value: Any) -> str:
    """Operator hint for Assignee on Support Queue."""
    text = str(value or '').strip()
    if not text:
        return 'Optional field assignee is empty for support_tickets.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'assignee' + ' is zero; confirm that is intentional for Support Queue.'
        return 'assignee' + ' holds ' + str(number) + ' in the support_tickets ledger.'
    if len(text) < 3:
        return 'assignee' + ' is unusually short; operators may misread the support_tickets list.'
    return 'assignee' + ' is populated (' + str(len(text)) + ' chars) for support_tickets.'


def describe_support_tickets_status(value: Any) -> str:
    """Operator hint for Status on Support Queue."""
    text = str(value or '').strip()
    if not text:
        return 'Required field status is empty for support_tickets.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'status' + ' is zero; confirm that is intentional for Support Queue.'
        return 'status' + ' holds ' + str(number) + ' in the support_tickets ledger.'
    if len(text) < 3:
        return 'status' + ' is unusually short; operators may misread the support_tickets list.'
    return 'status' + ' is populated (' + str(len(text)) + ' chars) for support_tickets.'


