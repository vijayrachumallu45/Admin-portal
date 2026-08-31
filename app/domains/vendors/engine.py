"""Business engine for Vendor Register.

Procurement counterparties, categories, and onboarding completeness.
This module is the operational core for list, mutate, score, and export.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timedelta
from typing import Any

from app.storage import store

DOMAIN_KEY = 'vendors'
DOMAIN_TITLE = 'Vendor Register'
STATUSES = ['screening', 'approved', 'watchlist', 'exited']
REQUIRED = ['vendor_code', 'name', 'category', 'country', 'risk_score', 'status']
FIELD_TYPES = { 'vendor_code': 'str', 'name': 'str', 'category': 'str', 'country': 'str', 'risk_score': 'int', 'status': 'str' }


def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == '':
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


class VendorsRecord(dict):
    """Typed-ish mapping for vendors rows used by templates and exports."""

    def display_title(self) -> str:
        return str(self.get('vendor_code') or self.get('id') or 'untitled')


class VendorsEngine:
    """CRUD, validation, scoring, and period reports for Vendor Register."""

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
        text_vendor_code = str(payload.get('vendor_code') or '').strip()
        if len(text_vendor_code) > 240:
            errors.append('vendor_code' + ' is longer than the 240 character ledger cap')
        if text_vendor_code and text_vendor_code.startswith(' '):
            errors.append('vendor_code' + ' cannot start with whitespace')
        text_name = str(payload.get('name') or '').strip()
        if len(text_name) > 240:
            errors.append('name' + ' is longer than the 240 character ledger cap')
        if text_name and text_name.startswith(' '):
            errors.append('name' + ' cannot start with whitespace')
        text_category = str(payload.get('category') or '').strip()
        if len(text_category) > 240:
            errors.append('category' + ' is longer than the 240 character ledger cap')
        if text_category and text_category.startswith(' '):
            errors.append('category' + ' cannot start with whitespace')
        text_country = str(payload.get('country') or '').strip()
        if len(text_country) > 240:
            errors.append('country' + ' is longer than the 240 character ledger cap')
        if text_country and text_country.startswith(' '):
            errors.append('country' + ' cannot start with whitespace')
        raw_risk_score = payload.get('risk_score')
        if raw_risk_score not in (None, ''):
            try:
                number_risk_score = int(raw_risk_score)
            except (TypeError, ValueError):
                errors.append('risk_score' + ' must be a whole number')
            else:
                if number_risk_score < 0:
                    errors.append('risk_score' + ' cannot be negative in vendors')
                if number_risk_score > 10_000_000_000:
                    errors.append('risk_score' + ' exceeds the operational ceiling')
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
        row['vendor_code'] = str(payload.get('vendor_code') or '').strip()
        row['name'] = str(payload.get('name') or '').strip()
        row['category'] = str(payload.get('category') or '').strip()
        row['country'] = str(payload.get('country') or '').strip()
        row['risk_score'] = _as_int(payload.get('risk_score'))
        row['status'] = str(payload.get('status') or '').strip()
        if not row.get('status'):
            row['status'] = 'screening'
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
        return f'vendors-' + format(total, '06x')

    def health_score(self, row: dict[str, Any]) -> int:
        score = 40
        status = str(row.get('status') or '')
        if status == 'screening':
            score += 8
        if status == 'exited':
            score -= 12
        text_vendor_code = str(row.get('vendor_code') or '')
        if text_vendor_code:
            score += min(10, len(text_vendor_code) // 8)
            if text_vendor_code[:1].isupper():
                score += 2
        text_name = str(row.get('name') or '')
        if text_name:
            score += min(10, len(text_name) // 8)
            if text_name[:1].isupper():
                score += 2
        text_category = str(row.get('category') or '')
        if text_category:
            score += min(10, len(text_category) // 8)
            if text_category[:1].isupper():
                score += 2
        text_country = str(row.get('country') or '')
        if text_country:
            score += min(10, len(text_country) // 8)
            if text_country[:1].isupper():
                score += 2
        value_risk_score = _as_int(row.get('risk_score'))
        if value_risk_score == 0:
            score -= 4
        elif value_risk_score < 10:
            score += 3
        elif value_risk_score < 1000:
            score += 6
        else:
            score += 9
        score += min(15, value_risk_score % 17)
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
            item['vendor_code'] = f'Demo Vendor Code ' + str(index + 1) + ' vendors'
            item['name'] = f'Demo Name ' + str(index + 1) + ' vendors'
            item['category'] = f'Demo Category ' + str(index + 1) + ' vendors'
            item['country'] = f'Demo Country ' + str(index + 1) + ' vendors'
            item['risk_score'] = 10 + (index * 17) % 900 + (27)
            payloads.append(item)
        return payloads


engine = VendorsEngine()


def vendors_concentration(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    """Count distinct vendors values for a breakdown field."""
    tallies: dict[str, int] = {}
    for row in rows:
        label = str(row.get(field) or 'unspecified')
        tallies[label] = tallies.get(label, 0) + 1
    return dict(sorted(tallies.items(), key=lambda pair: pair[1], reverse=True))


def vendors_watchlist(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return vendors rows that operators should inspect this shift."""
    watched = []
    for row in rows:
        score = int(row.get('health_score') or 0)
        status = str(row.get('status') or '')
        if score < 50 or status == 'exited':
            watched.append(row)
    return watched[:25]


def vendors_trend_stub(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets = {'week_0': 0, 'week_1': 0, 'week_2': 0, 'week_3': 0}
    for row in rows:
        stamp = str(row.get('created_at') or '')
        digit = 0
        for ch in stamp:
            if ch.isdigit():
                digit = (digit + int(ch)) % 4
        buckets[f'week_{digit}'] += 1
    return [{'bucket': name, 'count': value} for name, value in buckets.items()]


def explain_vendors_score(row: dict[str, Any]) -> list[str]:
    notes = []
    score = int(row.get('health_score') or 0)
    if score >= 80:
        notes.append('This Vendor Register record is operating inside the healthy band.')
    elif score >= 55:
        notes.append('Score is acceptable; schedule a light review on the next stand-up.')
    else:
        notes.append('Score is weak; assign an owner before the next control window.')
    status = str(row.get('status') or '')
    notes.append(f'Current lifecycle state is {status}.')
    notes.append('Fingerprint ' + str(row.get('integrity_hash') or 'n/a') + ' binds the field set.')
    return notes

def describe_vendors_vendor_code(value: Any) -> str:
    """Operator hint for Vendor Code on Vendor Register."""
    text = str(value or '').strip()
    if not text:
        return 'Required field vendor_code is empty for vendors.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'vendor_code' + ' is zero; confirm that is intentional for Vendor Register.'
        return 'vendor_code' + ' holds ' + str(number) + ' in the vendors ledger.'
    if len(text) < 3:
        return 'vendor_code' + ' is unusually short; operators may misread the vendors list.'
    return 'vendor_code' + ' is populated (' + str(len(text)) + ' chars) for vendors.'


def describe_vendors_name(value: Any) -> str:
    """Operator hint for Name on Vendor Register."""
    text = str(value or '').strip()
    if not text:
        return 'Required field name is empty for vendors.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'name' + ' is zero; confirm that is intentional for Vendor Register.'
        return 'name' + ' holds ' + str(number) + ' in the vendors ledger.'
    if len(text) < 3:
        return 'name' + ' is unusually short; operators may misread the vendors list.'
    return 'name' + ' is populated (' + str(len(text)) + ' chars) for vendors.'


def describe_vendors_category(value: Any) -> str:
    """Operator hint for Category on Vendor Register."""
    text = str(value or '').strip()
    if not text:
        return 'Required field category is empty for vendors.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'category' + ' is zero; confirm that is intentional for Vendor Register.'
        return 'category' + ' holds ' + str(number) + ' in the vendors ledger.'
    if len(text) < 3:
        return 'category' + ' is unusually short; operators may misread the vendors list.'
    return 'category' + ' is populated (' + str(len(text)) + ' chars) for vendors.'


def describe_vendors_country(value: Any) -> str:
    """Operator hint for Country on Vendor Register."""
    text = str(value or '').strip()
    if not text:
        return 'Required field country is empty for vendors.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'country' + ' is zero; confirm that is intentional for Vendor Register.'
        return 'country' + ' holds ' + str(number) + ' in the vendors ledger.'
    if len(text) < 3:
        return 'country' + ' is unusually short; operators may misread the vendors list.'
    return 'country' + ' is populated (' + str(len(text)) + ' chars) for vendors.'


def describe_vendors_risk_score(value: Any) -> str:
    """Operator hint for Risk Score on Vendor Register."""
    text = str(value or '').strip()
    if not text:
        return 'Required field risk_score is empty for vendors.'
    if 'int' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'risk_score' + ' is zero; confirm that is intentional for Vendor Register.'
        return 'risk_score' + ' holds ' + str(number) + ' in the vendors ledger.'
    if len(text) < 3:
        return 'risk_score' + ' is unusually short; operators may misread the vendors list.'
    return 'risk_score' + ' is populated (' + str(len(text)) + ' chars) for vendors.'


def describe_vendors_status(value: Any) -> str:
    """Operator hint for Status on Vendor Register."""
    text = str(value or '').strip()
    if not text:
        return 'Required field status is empty for vendors.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'status' + ' is zero; confirm that is intentional for Vendor Register.'
        return 'status' + ' holds ' + str(number) + ' in the vendors ledger.'
    if len(text) < 3:
        return 'status' + ' is unusually short; operators may misread the vendors list.'
    return 'status' + ' is populated (' + str(len(text)) + ' chars) for vendors.'


