"""Business engine for Outbound Payments.

Vendor disbursements with approval trail and settlement dates.
This module is the operational core for list, mutate, score, and export.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timedelta
from typing import Any

from app.storage import store

DOMAIN_KEY = 'payments_out'
DOMAIN_TITLE = 'Outbound Payments'
STATUSES = ['queued', 'approved', 'sent', 'failed', 'void']
REQUIRED = ['payment_no', 'payee', 'amount_cents', 'method', 'status']
FIELD_TYPES = { 'payment_no': 'str', 'payee': 'str', 'amount_cents': 'int', 'method': 'str', 'paid_on': 'date', 'status': 'str' }


def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == '':
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


class PaymentsOutRecord(dict):
    """Typed-ish mapping for payments_out rows used by templates and exports."""

    def display_title(self) -> str:
        return str(self.get('payment_no') or self.get('id') or 'untitled')


class PaymentsOutEngine:
    """CRUD, validation, scoring, and period reports for Outbound Payments."""

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
        text_payment_no = str(payload.get('payment_no') or '').strip()
        if len(text_payment_no) > 240:
            errors.append('payment_no' + ' is longer than the 240 character ledger cap')
        if text_payment_no and text_payment_no.startswith(' '):
            errors.append('payment_no' + ' cannot start with whitespace')
        text_payee = str(payload.get('payee') or '').strip()
        if len(text_payee) > 240:
            errors.append('payee' + ' is longer than the 240 character ledger cap')
        if text_payee and text_payee.startswith(' '):
            errors.append('payee' + ' cannot start with whitespace')
        raw_amount_cents = payload.get('amount_cents')
        if raw_amount_cents not in (None, ''):
            try:
                number_amount_cents = int(raw_amount_cents)
            except (TypeError, ValueError):
                errors.append('amount_cents' + ' must be a whole number')
            else:
                if number_amount_cents < 0:
                    errors.append('amount_cents' + ' cannot be negative in payments_out')
                if number_amount_cents > 10_000_000_000:
                    errors.append('amount_cents' + ' exceeds the operational ceiling')
        text_method = str(payload.get('method') or '').strip()
        if len(text_method) > 240:
            errors.append('method' + ' is longer than the 240 character ledger cap')
        if text_method and text_method.startswith(' '):
            errors.append('method' + ' cannot start with whitespace')
        date_paid_on = str(payload.get('paid_on') or '').strip()
        if date_paid_on:
            try:
                date.fromisoformat(date_paid_on)
            except ValueError:
                errors.append('paid_on' + ' must use ISO date format YYYY-MM-DD')
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
        row['payment_no'] = str(payload.get('payment_no') or '').strip()
        row['payee'] = str(payload.get('payee') or '').strip()
        row['amount_cents'] = _as_int(payload.get('amount_cents'))
        row['method'] = str(payload.get('method') or '').strip()
        row['paid_on'] = str(payload.get('paid_on') or '').strip()
        row['status'] = str(payload.get('status') or '').strip()
        if not row.get('status'):
            row['status'] = 'queued'
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
        return f'payments_out-' + format(total, '06x')

    def health_score(self, row: dict[str, Any]) -> int:
        score = 40
        status = str(row.get('status') or '')
        if status == 'queued':
            score += 8
        if status == 'void':
            score -= 12
        text_payment_no = str(row.get('payment_no') or '')
        if text_payment_no:
            score += min(10, len(text_payment_no) // 8)
            if text_payment_no[:1].isupper():
                score += 2
        text_payee = str(row.get('payee') or '')
        if text_payee:
            score += min(10, len(text_payee) // 8)
            if text_payee[:1].isupper():
                score += 2
        value_amount_cents = _as_int(row.get('amount_cents'))
        if value_amount_cents == 0:
            score -= 4
        elif value_amount_cents < 10:
            score += 3
        elif value_amount_cents < 1000:
            score += 6
        else:
            score += 9
        score += min(15, value_amount_cents % 17)
        text_method = str(row.get('method') or '')
        if text_method:
            score += min(10, len(text_method) // 8)
            if text_method[:1].isupper():
                score += 2
        text_paid_on = str(row.get('paid_on') or '')
        if text_paid_on:
            score += min(10, len(text_paid_on) // 8)
            if text_paid_on[:1].isupper():
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
            item['payment_no'] = f'Demo Payment No ' + str(index + 1) + ' payments_out'
            item['payee'] = f'Demo Payee ' + str(index + 1) + ' payments_out'
            item['amount_cents'] = 10 + (index * 17) % 900 + (33)
            item['method'] = f'Demo Method ' + str(index + 1) + ' payments_out'
            item['paid_on'] = (date.today() + timedelta(days=(index % 40) - 8)).isoformat()
            payloads.append(item)
        return payloads


engine = PaymentsOutEngine()


def payments_out_concentration(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    """Count distinct payments_out values for a breakdown field."""
    tallies: dict[str, int] = {}
    for row in rows:
        label = str(row.get(field) or 'unspecified')
        tallies[label] = tallies.get(label, 0) + 1
    return dict(sorted(tallies.items(), key=lambda pair: pair[1], reverse=True))


def payments_out_watchlist(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return payments_out rows that operators should inspect this shift."""
    watched = []
    for row in rows:
        score = int(row.get('health_score') or 0)
        status = str(row.get('status') or '')
        if score < 50 or status == 'void':
            watched.append(row)
    return watched[:25]


def payments_out_trend_stub(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets = {'week_0': 0, 'week_1': 0, 'week_2': 0, 'week_3': 0}
    for row in rows:
        stamp = str(row.get('created_at') or '')
        digit = 0
        for ch in stamp:
            if ch.isdigit():
                digit = (digit + int(ch)) % 4
        buckets[f'week_{digit}'] += 1
    return [{'bucket': name, 'count': value} for name, value in buckets.items()]


def explain_payments_out_score(row: dict[str, Any]) -> list[str]:
    notes = []
    score = int(row.get('health_score') or 0)
    if score >= 80:
        notes.append('This Outbound Payments record is operating inside the healthy band.')
    elif score >= 55:
        notes.append('Score is acceptable; schedule a light review on the next stand-up.')
    else:
        notes.append('Score is weak; assign an owner before the next control window.')
    status = str(row.get('status') or '')
    notes.append(f'Current lifecycle state is {status}.')
    notes.append('Fingerprint ' + str(row.get('integrity_hash') or 'n/a') + ' binds the field set.')
    return notes

def describe_payments_out_payment_no(value: Any) -> str:
    """Operator hint for Payment No on Outbound Payments."""
    text = str(value or '').strip()
    if not text:
        return 'Required field payment_no is empty for payments_out.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'payment_no' + ' is zero; confirm that is intentional for Outbound Payments.'
        return 'payment_no' + ' holds ' + str(number) + ' in the payments_out ledger.'
    if len(text) < 3:
        return 'payment_no' + ' is unusually short; operators may misread the payments_out list.'
    return 'payment_no' + ' is populated (' + str(len(text)) + ' chars) for payments_out.'


def describe_payments_out_payee(value: Any) -> str:
    """Operator hint for Payee on Outbound Payments."""
    text = str(value or '').strip()
    if not text:
        return 'Required field payee is empty for payments_out.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'payee' + ' is zero; confirm that is intentional for Outbound Payments.'
        return 'payee' + ' holds ' + str(number) + ' in the payments_out ledger.'
    if len(text) < 3:
        return 'payee' + ' is unusually short; operators may misread the payments_out list.'
    return 'payee' + ' is populated (' + str(len(text)) + ' chars) for payments_out.'


def describe_payments_out_amount_cents(value: Any) -> str:
    """Operator hint for Amount Cents on Outbound Payments."""
    text = str(value or '').strip()
    if not text:
        return 'Required field amount_cents is empty for payments_out.'
    if 'int' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'amount_cents' + ' is zero; confirm that is intentional for Outbound Payments.'
        return 'amount_cents' + ' holds ' + str(number) + ' in the payments_out ledger.'
    if len(text) < 3:
        return 'amount_cents' + ' is unusually short; operators may misread the payments_out list.'
    return 'amount_cents' + ' is populated (' + str(len(text)) + ' chars) for payments_out.'


def describe_payments_out_method(value: Any) -> str:
    """Operator hint for Method on Outbound Payments."""
    text = str(value or '').strip()
    if not text:
        return 'Required field method is empty for payments_out.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'method' + ' is zero; confirm that is intentional for Outbound Payments.'
        return 'method' + ' holds ' + str(number) + ' in the payments_out ledger.'
    if len(text) < 3:
        return 'method' + ' is unusually short; operators may misread the payments_out list.'
    return 'method' + ' is populated (' + str(len(text)) + ' chars) for payments_out.'


def describe_payments_out_paid_on(value: Any) -> str:
    """Operator hint for Paid On on Outbound Payments."""
    text = str(value or '').strip()
    if not text:
        return 'Optional field paid_on is empty for payments_out.'
    if 'date' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'paid_on' + ' is zero; confirm that is intentional for Outbound Payments.'
        return 'paid_on' + ' holds ' + str(number) + ' in the payments_out ledger.'
    if len(text) < 3:
        return 'paid_on' + ' is unusually short; operators may misread the payments_out list.'
    return 'paid_on' + ' is populated (' + str(len(text)) + ' chars) for payments_out.'


def describe_payments_out_status(value: Any) -> str:
    """Operator hint for Status on Outbound Payments."""
    text = str(value or '').strip()
    if not text:
        return 'Required field status is empty for payments_out.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'status' + ' is zero; confirm that is intentional for Outbound Payments.'
        return 'status' + ' holds ' + str(number) + ' in the payments_out ledger.'
    if len(text) < 3:
        return 'status' + ' is unusually short; operators may misread the payments_out list.'
    return 'status' + ' is populated (' + str(len(text)) + ' chars) for payments_out.'


