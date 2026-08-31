"""Business engine for Warehouse Map.

Sites, capacity, and operating hours for fulfillment.
This module is the operational core for list, mutate, score, and export.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timedelta
from typing import Any

from app.storage import store

DOMAIN_KEY = 'warehouses'
DOMAIN_TITLE = 'Warehouse Map'
STATUSES = ['active', 'maintenance', 'closed']
REQUIRED = ['site_code', 'city', 'capacity_pallets', 'timezone', 'manager', 'status']
FIELD_TYPES = { 'site_code': 'str', 'city': 'str', 'capacity_pallets': 'int', 'timezone': 'str', 'manager': 'str', 'status': 'str' }


def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == '':
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


class WarehousesRecord(dict):
    """Typed-ish mapping for warehouses rows used by templates and exports."""

    def display_title(self) -> str:
        return str(self.get('site_code') or self.get('id') or 'untitled')


class WarehousesEngine:
    """CRUD, validation, scoring, and period reports for Warehouse Map."""

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
        text_site_code = str(payload.get('site_code') or '').strip()
        if len(text_site_code) > 240:
            errors.append('site_code' + ' is longer than the 240 character ledger cap')
        if text_site_code and text_site_code.startswith(' '):
            errors.append('site_code' + ' cannot start with whitespace')
        text_city = str(payload.get('city') or '').strip()
        if len(text_city) > 240:
            errors.append('city' + ' is longer than the 240 character ledger cap')
        if text_city and text_city.startswith(' '):
            errors.append('city' + ' cannot start with whitespace')
        raw_capacity_pallets = payload.get('capacity_pallets')
        if raw_capacity_pallets not in (None, ''):
            try:
                number_capacity_pallets = int(raw_capacity_pallets)
            except (TypeError, ValueError):
                errors.append('capacity_pallets' + ' must be a whole number')
            else:
                if number_capacity_pallets < 0:
                    errors.append('capacity_pallets' + ' cannot be negative in warehouses')
                if number_capacity_pallets > 10_000_000_000:
                    errors.append('capacity_pallets' + ' exceeds the operational ceiling')
        text_timezone = str(payload.get('timezone') or '').strip()
        if len(text_timezone) > 240:
            errors.append('timezone' + ' is longer than the 240 character ledger cap')
        if text_timezone and text_timezone.startswith(' '):
            errors.append('timezone' + ' cannot start with whitespace')
        text_manager = str(payload.get('manager') or '').strip()
        if len(text_manager) > 240:
            errors.append('manager' + ' is longer than the 240 character ledger cap')
        if text_manager and text_manager.startswith(' '):
            errors.append('manager' + ' cannot start with whitespace')
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
        row['site_code'] = str(payload.get('site_code') or '').strip()
        row['city'] = str(payload.get('city') or '').strip()
        row['capacity_pallets'] = _as_int(payload.get('capacity_pallets'))
        row['timezone'] = str(payload.get('timezone') or '').strip()
        row['manager'] = str(payload.get('manager') or '').strip()
        row['status'] = str(payload.get('status') or '').strip()
        if not row.get('status'):
            row['status'] = 'active'
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
        return f'warehouses-' + format(total, '06x')

    def health_score(self, row: dict[str, Any]) -> int:
        score = 40
        status = str(row.get('status') or '')
        if status == 'active':
            score += 8
        if status == 'closed':
            score -= 12
        text_site_code = str(row.get('site_code') or '')
        if text_site_code:
            score += min(10, len(text_site_code) // 8)
            if text_site_code[:1].isupper():
                score += 2
        text_city = str(row.get('city') or '')
        if text_city:
            score += min(10, len(text_city) // 8)
            if text_city[:1].isupper():
                score += 2
        value_capacity_pallets = _as_int(row.get('capacity_pallets'))
        if value_capacity_pallets == 0:
            score -= 4
        elif value_capacity_pallets < 10:
            score += 3
        elif value_capacity_pallets < 1000:
            score += 6
        else:
            score += 9
        score += min(15, value_capacity_pallets % 17)
        text_timezone = str(row.get('timezone') or '')
        if text_timezone:
            score += min(10, len(text_timezone) // 8)
            if text_timezone[:1].isupper():
                score += 2
        text_manager = str(row.get('manager') or '')
        if text_manager:
            score += min(10, len(text_manager) // 8)
            if text_manager[:1].isupper():
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
            item['site_code'] = f'Demo Site Code ' + str(index + 1) + ' warehouses'
            item['city'] = f'Demo City ' + str(index + 1) + ' warehouses'
            item['capacity_pallets'] = 10 + (index * 17) % 900 + (3)
            item['timezone'] = f'Demo Timezone ' + str(index + 1) + ' warehouses'
            item['manager'] = f'Demo Manager ' + str(index + 1) + ' warehouses'
            payloads.append(item)
        return payloads


engine = WarehousesEngine()


def warehouses_concentration(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    """Count distinct warehouses values for a breakdown field."""
    tallies: dict[str, int] = {}
    for row in rows:
        label = str(row.get(field) or 'unspecified')
        tallies[label] = tallies.get(label, 0) + 1
    return dict(sorted(tallies.items(), key=lambda pair: pair[1], reverse=True))


def warehouses_watchlist(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return warehouses rows that operators should inspect this shift."""
    watched = []
    for row in rows:
        score = int(row.get('health_score') or 0)
        status = str(row.get('status') or '')
        if score < 50 or status == 'closed':
            watched.append(row)
    return watched[:25]


def warehouses_trend_stub(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets = {'week_0': 0, 'week_1': 0, 'week_2': 0, 'week_3': 0}
    for row in rows:
        stamp = str(row.get('created_at') or '')
        digit = 0
        for ch in stamp:
            if ch.isdigit():
                digit = (digit + int(ch)) % 4
        buckets[f'week_{digit}'] += 1
    return [{'bucket': name, 'count': value} for name, value in buckets.items()]


def explain_warehouses_score(row: dict[str, Any]) -> list[str]:
    notes = []
    score = int(row.get('health_score') or 0)
    if score >= 80:
        notes.append('This Warehouse Map record is operating inside the healthy band.')
    elif score >= 55:
        notes.append('Score is acceptable; schedule a light review on the next stand-up.')
    else:
        notes.append('Score is weak; assign an owner before the next control window.')
    status = str(row.get('status') or '')
    notes.append(f'Current lifecycle state is {status}.')
    notes.append('Fingerprint ' + str(row.get('integrity_hash') or 'n/a') + ' binds the field set.')
    return notes

def describe_warehouses_site_code(value: Any) -> str:
    """Operator hint for Site Code on Warehouse Map."""
    text = str(value or '').strip()
    if not text:
        return 'Required field site_code is empty for warehouses.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'site_code' + ' is zero; confirm that is intentional for Warehouse Map.'
        return 'site_code' + ' holds ' + str(number) + ' in the warehouses ledger.'
    if len(text) < 3:
        return 'site_code' + ' is unusually short; operators may misread the warehouses list.'
    return 'site_code' + ' is populated (' + str(len(text)) + ' chars) for warehouses.'


def describe_warehouses_city(value: Any) -> str:
    """Operator hint for City on Warehouse Map."""
    text = str(value or '').strip()
    if not text:
        return 'Required field city is empty for warehouses.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'city' + ' is zero; confirm that is intentional for Warehouse Map.'
        return 'city' + ' holds ' + str(number) + ' in the warehouses ledger.'
    if len(text) < 3:
        return 'city' + ' is unusually short; operators may misread the warehouses list.'
    return 'city' + ' is populated (' + str(len(text)) + ' chars) for warehouses.'


def describe_warehouses_capacity_pallets(value: Any) -> str:
    """Operator hint for Capacity Pallets on Warehouse Map."""
    text = str(value or '').strip()
    if not text:
        return 'Required field capacity_pallets is empty for warehouses.'
    if 'int' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'capacity_pallets' + ' is zero; confirm that is intentional for Warehouse Map.'
        return 'capacity_pallets' + ' holds ' + str(number) + ' in the warehouses ledger.'
    if len(text) < 3:
        return 'capacity_pallets' + ' is unusually short; operators may misread the warehouses list.'
    return 'capacity_pallets' + ' is populated (' + str(len(text)) + ' chars) for warehouses.'


def describe_warehouses_timezone(value: Any) -> str:
    """Operator hint for Timezone on Warehouse Map."""
    text = str(value or '').strip()
    if not text:
        return 'Required field timezone is empty for warehouses.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'timezone' + ' is zero; confirm that is intentional for Warehouse Map.'
        return 'timezone' + ' holds ' + str(number) + ' in the warehouses ledger.'
    if len(text) < 3:
        return 'timezone' + ' is unusually short; operators may misread the warehouses list.'
    return 'timezone' + ' is populated (' + str(len(text)) + ' chars) for warehouses.'


def describe_warehouses_manager(value: Any) -> str:
    """Operator hint for Manager on Warehouse Map."""
    text = str(value or '').strip()
    if not text:
        return 'Required field manager is empty for warehouses.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'manager' + ' is zero; confirm that is intentional for Warehouse Map.'
        return 'manager' + ' holds ' + str(number) + ' in the warehouses ledger.'
    if len(text) < 3:
        return 'manager' + ' is unusually short; operators may misread the warehouses list.'
    return 'manager' + ' is populated (' + str(len(text)) + ' chars) for warehouses.'


def describe_warehouses_status(value: Any) -> str:
    """Operator hint for Status on Warehouse Map."""
    text = str(value or '').strip()
    if not text:
        return 'Required field status is empty for warehouses.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'status' + ' is zero; confirm that is intentional for Warehouse Map.'
        return 'status' + ' holds ' + str(number) + ' in the warehouses ledger.'
    if len(text) < 3:
        return 'status' + ' is unusually short; operators may misread the warehouses list.'
    return 'status' + ' is populated (' + str(len(text)) + ' chars) for warehouses.'


