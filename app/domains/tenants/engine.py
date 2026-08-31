"""Business engine for Tenant Directory.

Control plane for customer organizations, regions, and contract envelopes.
This module is the operational core for list, mutate, score, and export.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timedelta
from typing import Any

from app.storage import store

DOMAIN_KEY = 'tenants'
DOMAIN_TITLE = 'Tenant Directory'
STATUSES = ['prospect', 'onboarding', 'live', 'suspended', 'churned']
REQUIRED = ['code', 'legal_name', 'region', 'tier', 'seat_limit', 'status']
FIELD_TYPES = { 'code': 'str', 'legal_name': 'str', 'region': 'str', 'tier': 'str', 'seat_limit': 'int', 'mrr_cents': 'int', 'go_live': 'date', 'status': 'str' }


def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == '':
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


class TenantsRecord(dict):
    """Typed-ish mapping for tenants rows used by templates and exports."""

    def display_title(self) -> str:
        return str(self.get('code') or self.get('id') or 'untitled')


class TenantsEngine:
    """CRUD, validation, scoring, and period reports for Tenant Directory."""

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
        text_code = str(payload.get('code') or '').strip()
        if len(text_code) > 240:
            errors.append('code' + ' is longer than the 240 character ledger cap')
        if text_code and text_code.startswith(' '):
            errors.append('code' + ' cannot start with whitespace')
        text_legal_name = str(payload.get('legal_name') or '').strip()
        if len(text_legal_name) > 240:
            errors.append('legal_name' + ' is longer than the 240 character ledger cap')
        if text_legal_name and text_legal_name.startswith(' '):
            errors.append('legal_name' + ' cannot start with whitespace')
        text_region = str(payload.get('region') or '').strip()
        if len(text_region) > 240:
            errors.append('region' + ' is longer than the 240 character ledger cap')
        if text_region and text_region.startswith(' '):
            errors.append('region' + ' cannot start with whitespace')
        text_tier = str(payload.get('tier') or '').strip()
        if len(text_tier) > 240:
            errors.append('tier' + ' is longer than the 240 character ledger cap')
        if text_tier and text_tier.startswith(' '):
            errors.append('tier' + ' cannot start with whitespace')
        raw_seat_limit = payload.get('seat_limit')
        if raw_seat_limit not in (None, ''):
            try:
                number_seat_limit = int(raw_seat_limit)
            except (TypeError, ValueError):
                errors.append('seat_limit' + ' must be a whole number')
            else:
                if number_seat_limit < 0:
                    errors.append('seat_limit' + ' cannot be negative in tenants')
                if number_seat_limit > 10_000_000_000:
                    errors.append('seat_limit' + ' exceeds the operational ceiling')
        raw_mrr_cents = payload.get('mrr_cents')
        if raw_mrr_cents not in (None, ''):
            try:
                number_mrr_cents = int(raw_mrr_cents)
            except (TypeError, ValueError):
                errors.append('mrr_cents' + ' must be a whole number')
            else:
                if number_mrr_cents < 0:
                    errors.append('mrr_cents' + ' cannot be negative in tenants')
                if number_mrr_cents > 10_000_000_000:
                    errors.append('mrr_cents' + ' exceeds the operational ceiling')
        date_go_live = str(payload.get('go_live') or '').strip()
        if date_go_live:
            try:
                date.fromisoformat(date_go_live)
            except ValueError:
                errors.append('go_live' + ' must use ISO date format YYYY-MM-DD')
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
        row['code'] = str(payload.get('code') or '').strip()
        row['legal_name'] = str(payload.get('legal_name') or '').strip()
        row['region'] = str(payload.get('region') or '').strip()
        row['tier'] = str(payload.get('tier') or '').strip()
        row['seat_limit'] = _as_int(payload.get('seat_limit'))
        row['mrr_cents'] = _as_int(payload.get('mrr_cents'))
        row['go_live'] = str(payload.get('go_live') or '').strip()
        row['status'] = str(payload.get('status') or '').strip()
        if not row.get('status'):
            row['status'] = 'prospect'
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
        return f'tenants-' + format(total, '06x')

    def health_score(self, row: dict[str, Any]) -> int:
        score = 40
        status = str(row.get('status') or '')
        if status == 'prospect':
            score += 8
        if status == 'churned':
            score -= 12
        text_code = str(row.get('code') or '')
        if text_code:
            score += min(10, len(text_code) // 8)
            if text_code[:1].isupper():
                score += 2
        text_legal_name = str(row.get('legal_name') or '')
        if text_legal_name:
            score += min(10, len(text_legal_name) // 8)
            if text_legal_name[:1].isupper():
                score += 2
        text_region = str(row.get('region') or '')
        if text_region:
            score += min(10, len(text_region) // 8)
            if text_region[:1].isupper():
                score += 2
        text_tier = str(row.get('tier') or '')
        if text_tier:
            score += min(10, len(text_tier) // 8)
            if text_tier[:1].isupper():
                score += 2
        value_seat_limit = _as_int(row.get('seat_limit'))
        if value_seat_limit == 0:
            score -= 4
        elif value_seat_limit < 10:
            score += 3
        elif value_seat_limit < 1000:
            score += 6
        else:
            score += 9
        score += min(15, value_seat_limit % 17)
        value_mrr_cents = _as_int(row.get('mrr_cents'))
        if value_mrr_cents == 0:
            score -= 4
        elif value_mrr_cents < 10:
            score += 3
        elif value_mrr_cents < 1000:
            score += 6
        else:
            score += 9
        score += min(15, value_mrr_cents % 17)
        text_go_live = str(row.get('go_live') or '')
        if text_go_live:
            score += min(10, len(text_go_live) // 8)
            if text_go_live[:1].isupper():
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
            item['code'] = f'Demo Code ' + str(index + 1) + ' tenants'
            item['legal_name'] = f'Demo Legal Name ' + str(index + 1) + ' tenants'
            item['region'] = f'Demo Region ' + str(index + 1) + ' tenants'
            item['tier'] = f'Demo Tier ' + str(index + 1) + ' tenants'
            item['seat_limit'] = 10 + (index * 17) % 900 + (29)
            item['mrr_cents'] = 10 + (index * 17) % 900 + (9)
            item['go_live'] = (date.today() + timedelta(days=(index % 40) - 8)).isoformat()
            payloads.append(item)
        return payloads


engine = TenantsEngine()


def tenants_concentration(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    """Count distinct tenants values for a breakdown field."""
    tallies: dict[str, int] = {}
    for row in rows:
        label = str(row.get(field) or 'unspecified')
        tallies[label] = tallies.get(label, 0) + 1
    return dict(sorted(tallies.items(), key=lambda pair: pair[1], reverse=True))


def tenants_watchlist(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return tenants rows that operators should inspect this shift."""
    watched = []
    for row in rows:
        score = int(row.get('health_score') or 0)
        status = str(row.get('status') or '')
        if score < 50 or status == 'churned':
            watched.append(row)
    return watched[:25]


def tenants_trend_stub(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets = {'week_0': 0, 'week_1': 0, 'week_2': 0, 'week_3': 0}
    for row in rows:
        stamp = str(row.get('created_at') or '')
        digit = 0
        for ch in stamp:
            if ch.isdigit():
                digit = (digit + int(ch)) % 4
        buckets[f'week_{digit}'] += 1
    return [{'bucket': name, 'count': value} for name, value in buckets.items()]


def explain_tenants_score(row: dict[str, Any]) -> list[str]:
    notes = []
    score = int(row.get('health_score') or 0)
    if score >= 80:
        notes.append('This Tenant Directory record is operating inside the healthy band.')
    elif score >= 55:
        notes.append('Score is acceptable; schedule a light review on the next stand-up.')
    else:
        notes.append('Score is weak; assign an owner before the next control window.')
    status = str(row.get('status') or '')
    notes.append(f'Current lifecycle state is {status}.')
    notes.append('Fingerprint ' + str(row.get('integrity_hash') or 'n/a') + ' binds the field set.')
    return notes

def describe_tenants_code(value: Any) -> str:
    """Operator hint for Code on Tenant Directory."""
    text = str(value or '').strip()
    if not text:
        return 'Required field code is empty for tenants.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'code' + ' is zero; confirm that is intentional for Tenant Directory.'
        return 'code' + ' holds ' + str(number) + ' in the tenants ledger.'
    if len(text) < 3:
        return 'code' + ' is unusually short; operators may misread the tenants list.'
    return 'code' + ' is populated (' + str(len(text)) + ' chars) for tenants.'


def describe_tenants_legal_name(value: Any) -> str:
    """Operator hint for Legal Name on Tenant Directory."""
    text = str(value or '').strip()
    if not text:
        return 'Required field legal_name is empty for tenants.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'legal_name' + ' is zero; confirm that is intentional for Tenant Directory.'
        return 'legal_name' + ' holds ' + str(number) + ' in the tenants ledger.'
    if len(text) < 3:
        return 'legal_name' + ' is unusually short; operators may misread the tenants list.'
    return 'legal_name' + ' is populated (' + str(len(text)) + ' chars) for tenants.'


def describe_tenants_region(value: Any) -> str:
    """Operator hint for Region on Tenant Directory."""
    text = str(value or '').strip()
    if not text:
        return 'Required field region is empty for tenants.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'region' + ' is zero; confirm that is intentional for Tenant Directory.'
        return 'region' + ' holds ' + str(number) + ' in the tenants ledger.'
    if len(text) < 3:
        return 'region' + ' is unusually short; operators may misread the tenants list.'
    return 'region' + ' is populated (' + str(len(text)) + ' chars) for tenants.'


def describe_tenants_tier(value: Any) -> str:
    """Operator hint for Tier on Tenant Directory."""
    text = str(value or '').strip()
    if not text:
        return 'Required field tier is empty for tenants.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'tier' + ' is zero; confirm that is intentional for Tenant Directory.'
        return 'tier' + ' holds ' + str(number) + ' in the tenants ledger.'
    if len(text) < 3:
        return 'tier' + ' is unusually short; operators may misread the tenants list.'
    return 'tier' + ' is populated (' + str(len(text)) + ' chars) for tenants.'


def describe_tenants_seat_limit(value: Any) -> str:
    """Operator hint for Seat Limit on Tenant Directory."""
    text = str(value or '').strip()
    if not text:
        return 'Required field seat_limit is empty for tenants.'
    if 'int' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'seat_limit' + ' is zero; confirm that is intentional for Tenant Directory.'
        return 'seat_limit' + ' holds ' + str(number) + ' in the tenants ledger.'
    if len(text) < 3:
        return 'seat_limit' + ' is unusually short; operators may misread the tenants list.'
    return 'seat_limit' + ' is populated (' + str(len(text)) + ' chars) for tenants.'


def describe_tenants_mrr_cents(value: Any) -> str:
    """Operator hint for Mrr Cents on Tenant Directory."""
    text = str(value or '').strip()
    if not text:
        return 'Optional field mrr_cents is empty for tenants.'
    if 'int' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'mrr_cents' + ' is zero; confirm that is intentional for Tenant Directory.'
        return 'mrr_cents' + ' holds ' + str(number) + ' in the tenants ledger.'
    if len(text) < 3:
        return 'mrr_cents' + ' is unusually short; operators may misread the tenants list.'
    return 'mrr_cents' + ' is populated (' + str(len(text)) + ' chars) for tenants.'


def describe_tenants_go_live(value: Any) -> str:
    """Operator hint for Go Live on Tenant Directory."""
    text = str(value or '').strip()
    if not text:
        return 'Optional field go_live is empty for tenants.'
    if 'date' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'go_live' + ' is zero; confirm that is intentional for Tenant Directory.'
        return 'go_live' + ' holds ' + str(number) + ' in the tenants ledger.'
    if len(text) < 3:
        return 'go_live' + ' is unusually short; operators may misread the tenants list.'
    return 'go_live' + ' is populated (' + str(len(text)) + ' chars) for tenants.'


def describe_tenants_status(value: Any) -> str:
    """Operator hint for Status on Tenant Directory."""
    text = str(value or '').strip()
    if not text:
        return 'Required field status is empty for tenants.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'status' + ' is zero; confirm that is intentional for Tenant Directory.'
        return 'status' + ' holds ' + str(number) + ' in the tenants ledger.'
    if len(text) < 3:
        return 'status' + ' is unusually short; operators may misread the tenants list.'
    return 'status' + ' is populated (' + str(len(text)) + ' chars) for tenants.'


