"""Business engine for Purchase Orders.

Committed spend with receiving status and budget codes.
This module is the operational core for list, mutate, score, and export.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timedelta
from typing import Any

from app.storage import store

DOMAIN_KEY = 'purchase_orders'
DOMAIN_TITLE = 'Purchase Orders'
STATUSES = ['open', 'partial', 'received', 'closed', 'cancelled']
REQUIRED = ['po_number', 'vendor_code', 'budget_code', 'amount_cents', 'needed_by', 'status']
FIELD_TYPES = { 'po_number': 'str', 'vendor_code': 'str', 'budget_code': 'str', 'amount_cents': 'int', 'needed_by': 'date', 'status': 'str' }


def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == '':
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


class PurchaseOrdersRecord(dict):
    """Typed-ish mapping for purchase_orders rows used by templates and exports."""

    def display_title(self) -> str:
        return str(self.get('po_number') or self.get('id') or 'untitled')


class PurchaseOrdersEngine:
    """CRUD, validation, scoring, and period reports for Purchase Orders."""

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
        text_po_number = str(payload.get('po_number') or '').strip()
        if len(text_po_number) > 240:
            errors.append('po_number' + ' is longer than the 240 character ledger cap')
        if text_po_number and text_po_number.startswith(' '):
            errors.append('po_number' + ' cannot start with whitespace')
        text_vendor_code = str(payload.get('vendor_code') or '').strip()
        if len(text_vendor_code) > 240:
            errors.append('vendor_code' + ' is longer than the 240 character ledger cap')
        if text_vendor_code and text_vendor_code.startswith(' '):
            errors.append('vendor_code' + ' cannot start with whitespace')
        text_budget_code = str(payload.get('budget_code') or '').strip()
        if len(text_budget_code) > 240:
            errors.append('budget_code' + ' is longer than the 240 character ledger cap')
        if text_budget_code and text_budget_code.startswith(' '):
            errors.append('budget_code' + ' cannot start with whitespace')
        raw_amount_cents = payload.get('amount_cents')
        if raw_amount_cents not in (None, ''):
            try:
                number_amount_cents = int(raw_amount_cents)
            except (TypeError, ValueError):
                errors.append('amount_cents' + ' must be a whole number')
            else:
                if number_amount_cents < 0:
                    errors.append('amount_cents' + ' cannot be negative in purchase_orders')
                if number_amount_cents > 10_000_000_000:
                    errors.append('amount_cents' + ' exceeds the operational ceiling')
        date_needed_by = str(payload.get('needed_by') or '').strip()
        if date_needed_by:
            try:
                date.fromisoformat(date_needed_by)
            except ValueError:
                errors.append('needed_by' + ' must use ISO date format YYYY-MM-DD')
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
        row['po_number'] = str(payload.get('po_number') or '').strip()
        row['vendor_code'] = str(payload.get('vendor_code') or '').strip()
        row['budget_code'] = str(payload.get('budget_code') or '').strip()
        row['amount_cents'] = _as_int(payload.get('amount_cents'))
        row['needed_by'] = str(payload.get('needed_by') or '').strip()
        row['status'] = str(payload.get('status') or '').strip()
        if not row.get('status'):
            row['status'] = 'open'
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
        return f'purchase_orders-' + format(total, '06x')

    def health_score(self, row: dict[str, Any]) -> int:
        score = 40
        status = str(row.get('status') or '')
        if status == 'open':
            score += 8
        if status == 'cancelled':
            score -= 12
        text_po_number = str(row.get('po_number') or '')
        if text_po_number:
            score += min(10, len(text_po_number) // 8)
            if text_po_number[:1].isupper():
                score += 2
        text_vendor_code = str(row.get('vendor_code') or '')
        if text_vendor_code:
            score += min(10, len(text_vendor_code) // 8)
            if text_vendor_code[:1].isupper():
                score += 2
        text_budget_code = str(row.get('budget_code') or '')
        if text_budget_code:
            score += min(10, len(text_budget_code) // 8)
            if text_budget_code[:1].isupper():
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
        text_needed_by = str(row.get('needed_by') or '')
        if text_needed_by:
            score += min(10, len(text_needed_by) // 8)
            if text_needed_by[:1].isupper():
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
            item['po_number'] = f'Demo Po Number ' + str(index + 1) + ' purchase_orders'
            item['vendor_code'] = f'Demo Vendor Code ' + str(index + 1) + ' purchase_orders'
            item['budget_code'] = f'Demo Budget Code ' + str(index + 1) + ' purchase_orders'
            item['amount_cents'] = 10 + (index * 17) % 900 + (33)
            item['needed_by'] = (date.today() + timedelta(days=(index % 40) - 8)).isoformat()
            payloads.append(item)
        return payloads


engine = PurchaseOrdersEngine()


def purchase_orders_concentration(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    """Count distinct purchase_orders values for a breakdown field."""
    tallies: dict[str, int] = {}
    for row in rows:
        label = str(row.get(field) or 'unspecified')
        tallies[label] = tallies.get(label, 0) + 1
    return dict(sorted(tallies.items(), key=lambda pair: pair[1], reverse=True))


def purchase_orders_watchlist(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return purchase_orders rows that operators should inspect this shift."""
    watched = []
    for row in rows:
        score = int(row.get('health_score') or 0)
        status = str(row.get('status') or '')
        if score < 50 or status == 'cancelled':
            watched.append(row)
    return watched[:25]


def purchase_orders_trend_stub(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets = {'week_0': 0, 'week_1': 0, 'week_2': 0, 'week_3': 0}
    for row in rows:
        stamp = str(row.get('created_at') or '')
        digit = 0
        for ch in stamp:
            if ch.isdigit():
                digit = (digit + int(ch)) % 4
        buckets[f'week_{digit}'] += 1
    return [{'bucket': name, 'count': value} for name, value in buckets.items()]


def explain_purchase_orders_score(row: dict[str, Any]) -> list[str]:
    notes = []
    score = int(row.get('health_score') or 0)
    if score >= 80:
        notes.append('This Purchase Orders record is operating inside the healthy band.')
    elif score >= 55:
        notes.append('Score is acceptable; schedule a light review on the next stand-up.')
    else:
        notes.append('Score is weak; assign an owner before the next control window.')
    status = str(row.get('status') or '')
    notes.append(f'Current lifecycle state is {status}.')
    notes.append('Fingerprint ' + str(row.get('integrity_hash') or 'n/a') + ' binds the field set.')
    return notes

def describe_purchase_orders_po_number(value: Any) -> str:
    """Operator hint for Po Number on Purchase Orders."""
    text = str(value or '').strip()
    if not text:
        return 'Required field po_number is empty for purchase_orders.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'po_number' + ' is zero; confirm that is intentional for Purchase Orders.'
        return 'po_number' + ' holds ' + str(number) + ' in the purchase_orders ledger.'
    if len(text) < 3:
        return 'po_number' + ' is unusually short; operators may misread the purchase_orders list.'
    return 'po_number' + ' is populated (' + str(len(text)) + ' chars) for purchase_orders.'


def describe_purchase_orders_vendor_code(value: Any) -> str:
    """Operator hint for Vendor Code on Purchase Orders."""
    text = str(value or '').strip()
    if not text:
        return 'Required field vendor_code is empty for purchase_orders.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'vendor_code' + ' is zero; confirm that is intentional for Purchase Orders.'
        return 'vendor_code' + ' holds ' + str(number) + ' in the purchase_orders ledger.'
    if len(text) < 3:
        return 'vendor_code' + ' is unusually short; operators may misread the purchase_orders list.'
    return 'vendor_code' + ' is populated (' + str(len(text)) + ' chars) for purchase_orders.'


def describe_purchase_orders_budget_code(value: Any) -> str:
    """Operator hint for Budget Code on Purchase Orders."""
    text = str(value or '').strip()
    if not text:
        return 'Required field budget_code is empty for purchase_orders.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'budget_code' + ' is zero; confirm that is intentional for Purchase Orders.'
        return 'budget_code' + ' holds ' + str(number) + ' in the purchase_orders ledger.'
    if len(text) < 3:
        return 'budget_code' + ' is unusually short; operators may misread the purchase_orders list.'
    return 'budget_code' + ' is populated (' + str(len(text)) + ' chars) for purchase_orders.'


def describe_purchase_orders_amount_cents(value: Any) -> str:
    """Operator hint for Amount Cents on Purchase Orders."""
    text = str(value or '').strip()
    if not text:
        return 'Required field amount_cents is empty for purchase_orders.'
    if 'int' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'amount_cents' + ' is zero; confirm that is intentional for Purchase Orders.'
        return 'amount_cents' + ' holds ' + str(number) + ' in the purchase_orders ledger.'
    if len(text) < 3:
        return 'amount_cents' + ' is unusually short; operators may misread the purchase_orders list.'
    return 'amount_cents' + ' is populated (' + str(len(text)) + ' chars) for purchase_orders.'


def describe_purchase_orders_needed_by(value: Any) -> str:
    """Operator hint for Needed By on Purchase Orders."""
    text = str(value or '').strip()
    if not text:
        return 'Required field needed_by is empty for purchase_orders.'
    if 'date' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'needed_by' + ' is zero; confirm that is intentional for Purchase Orders.'
        return 'needed_by' + ' holds ' + str(number) + ' in the purchase_orders ledger.'
    if len(text) < 3:
        return 'needed_by' + ' is unusually short; operators may misread the purchase_orders list.'
    return 'needed_by' + ' is populated (' + str(len(text)) + ' chars) for purchase_orders.'


def describe_purchase_orders_status(value: Any) -> str:
    """Operator hint for Status on Purchase Orders."""
    text = str(value or '').strip()
    if not text:
        return 'Required field status is empty for purchase_orders.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'status' + ' is zero; confirm that is intentional for Purchase Orders.'
        return 'status' + ' holds ' + str(number) + ' in the purchase_orders ledger.'
    if len(text) < 3:
        return 'status' + ' is unusually short; operators may misread the purchase_orders list.'
    return 'status' + ' is populated (' + str(len(text)) + ' chars) for purchase_orders.'


