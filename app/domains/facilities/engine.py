"""Business engine for Facilities.

Offices and plants with occupancy and safety owners.
This module is the operational core for list, mutate, score, and export.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timedelta
from typing import Any

from app.storage import store

DOMAIN_KEY = 'facilities'
DOMAIN_TITLE = 'Facilities'
STATUSES = ['open', 'limited', 'closed']
REQUIRED = ['site_code', 'address', 'capacity', 'safety_owner', 'status']
FIELD_TYPES = { 'site_code': 'str', 'address': 'str', 'capacity': 'int', 'safety_owner': 'str', 'status': 'str' }


def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == '':
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


class FacilitiesRecord(dict):
    """Typed-ish mapping for facilities rows used by templates and exports."""

    def display_title(self) -> str:
        return str(self.get('site_code') or self.get('id') or 'untitled')


class FacilitiesEngine:
    """CRUD, validation, scoring, and period reports for Facilities."""

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
        text_address = str(payload.get('address') or '').strip()
        if len(text_address) > 240:
            errors.append('address' + ' is longer than the 240 character ledger cap')
        if text_address and text_address.startswith(' '):
            errors.append('address' + ' cannot start with whitespace')
        raw_capacity = payload.get('capacity')
        if raw_capacity not in (None, ''):
            try:
                number_capacity = int(raw_capacity)
            except (TypeError, ValueError):
                errors.append('capacity' + ' must be a whole number')
            else:
                if number_capacity < 0:
                    errors.append('capacity' + ' cannot be negative in facilities')
                if number_capacity > 10_000_000_000:
                    errors.append('capacity' + ' exceeds the operational ceiling')
        text_safety_owner = str(payload.get('safety_owner') or '').strip()
        if len(text_safety_owner) > 240:
            errors.append('safety_owner' + ' is longer than the 240 character ledger cap')
        if text_safety_owner and text_safety_owner.startswith(' '):
            errors.append('safety_owner' + ' cannot start with whitespace')
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
        row['address'] = str(payload.get('address') or '').strip()
        row['capacity'] = _as_int(payload.get('capacity'))
        row['safety_owner'] = str(payload.get('safety_owner') or '').strip()
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
        return f'facilities-' + format(total, '06x')

    def health_score(self, row: dict[str, Any]) -> int:
        score = 40
        status = str(row.get('status') or '')
        if status == 'open':
            score += 8
        if status == 'closed':
            score -= 12
        text_site_code = str(row.get('site_code') or '')
        if text_site_code:
            score += min(10, len(text_site_code) // 8)
            if text_site_code[:1].isupper():
                score += 2
        text_address = str(row.get('address') or '')
        if text_address:
            score += min(10, len(text_address) // 8)
            if text_address[:1].isupper():
                score += 2
        value_capacity = _as_int(row.get('capacity'))
        if value_capacity == 0:
            score -= 4
        elif value_capacity < 10:
            score += 3
        elif value_capacity < 1000:
            score += 6
        else:
            score += 9
        score += min(15, value_capacity % 17)
        text_safety_owner = str(row.get('safety_owner') or '')
        if text_safety_owner:
            score += min(10, len(text_safety_owner) // 8)
            if text_safety_owner[:1].isupper():
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
            item['site_code'] = f'Demo Site Code ' + str(index + 1) + ' facilities'
            item['address'] = f'Demo Address ' + str(index + 1) + ' facilities'
            item['capacity'] = 10 + (index * 17) % 900 + (33)
            item['safety_owner'] = f'Demo Safety Owner ' + str(index + 1) + ' facilities'
            payloads.append(item)
        return payloads


engine = FacilitiesEngine()


def facilities_concentration(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    """Count distinct facilities values for a breakdown field."""
    tallies: dict[str, int] = {}
    for row in rows:
        label = str(row.get(field) or 'unspecified')
        tallies[label] = tallies.get(label, 0) + 1
    return dict(sorted(tallies.items(), key=lambda pair: pair[1], reverse=True))


def facilities_watchlist(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return facilities rows that operators should inspect this shift."""
    watched = []
    for row in rows:
        score = int(row.get('health_score') or 0)
        status = str(row.get('status') or '')
        if score < 50 or status == 'closed':
            watched.append(row)
    return watched[:25]


def facilities_trend_stub(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets = {'week_0': 0, 'week_1': 0, 'week_2': 0, 'week_3': 0}
    for row in rows:
        stamp = str(row.get('created_at') or '')
        digit = 0
        for ch in stamp:
            if ch.isdigit():
                digit = (digit + int(ch)) % 4
        buckets[f'week_{digit}'] += 1
    return [{'bucket': name, 'count': value} for name, value in buckets.items()]


def explain_facilities_score(row: dict[str, Any]) -> list[str]:
    notes = []
    score = int(row.get('health_score') or 0)
    if score >= 80:
        notes.append('This Facilities record is operating inside the healthy band.')
    elif score >= 55:
        notes.append('Score is acceptable; schedule a light review on the next stand-up.')
    else:
        notes.append('Score is weak; assign an owner before the next control window.')
    status = str(row.get('status') or '')
    notes.append(f'Current lifecycle state is {status}.')
    notes.append('Fingerprint ' + str(row.get('integrity_hash') or 'n/a') + ' binds the field set.')
    return notes

def describe_facilities_site_code(value: Any) -> str:
    """Operator hint for Site Code on Facilities."""
    text = str(value or '').strip()
    if not text:
        return 'Required field site_code is empty for facilities.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'site_code' + ' is zero; confirm that is intentional for Facilities.'
        return 'site_code' + ' holds ' + str(number) + ' in the facilities ledger.'
    if len(text) < 3:
        return 'site_code' + ' is unusually short; operators may misread the facilities list.'
    return 'site_code' + ' is populated (' + str(len(text)) + ' chars) for facilities.'


def describe_facilities_address(value: Any) -> str:
    """Operator hint for Address on Facilities."""
    text = str(value or '').strip()
    if not text:
        return 'Required field address is empty for facilities.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'address' + ' is zero; confirm that is intentional for Facilities.'
        return 'address' + ' holds ' + str(number) + ' in the facilities ledger.'
    if len(text) < 3:
        return 'address' + ' is unusually short; operators may misread the facilities list.'
    return 'address' + ' is populated (' + str(len(text)) + ' chars) for facilities.'


def describe_facilities_capacity(value: Any) -> str:
    """Operator hint for Capacity on Facilities."""
    text = str(value or '').strip()
    if not text:
        return 'Required field capacity is empty for facilities.'
    if 'int' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'capacity' + ' is zero; confirm that is intentional for Facilities.'
        return 'capacity' + ' holds ' + str(number) + ' in the facilities ledger.'
    if len(text) < 3:
        return 'capacity' + ' is unusually short; operators may misread the facilities list.'
    return 'capacity' + ' is populated (' + str(len(text)) + ' chars) for facilities.'


def describe_facilities_safety_owner(value: Any) -> str:
    """Operator hint for Safety Owner on Facilities."""
    text = str(value or '').strip()
    if not text:
        return 'Required field safety_owner is empty for facilities.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'safety_owner' + ' is zero; confirm that is intentional for Facilities.'
        return 'safety_owner' + ' holds ' + str(number) + ' in the facilities ledger.'
    if len(text) < 3:
        return 'safety_owner' + ' is unusually short; operators may misread the facilities list.'
    return 'safety_owner' + ' is populated (' + str(len(text)) + ' chars) for facilities.'


def describe_facilities_status(value: Any) -> str:
    """Operator hint for Status on Facilities."""
    text = str(value or '').strip()
    if not text:
        return 'Required field status is empty for facilities.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'status' + ' is zero; confirm that is intentional for Facilities.'
        return 'status' + ' holds ' + str(number) + ' in the facilities ledger.'
    if len(text) < 3:
        return 'status' + ' is unusually short; operators may misread the facilities list.'
    return 'status' + ' is populated (' + str(len(text)) + ' chars) for facilities.'


