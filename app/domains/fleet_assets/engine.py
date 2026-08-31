"""Business engine for Fleet Assets.

Vehicles and equipment with service intervals.
This module is the operational core for list, mutate, score, and export.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timedelta
from typing import Any

from app.storage import store

DOMAIN_KEY = 'fleet_assets'
DOMAIN_TITLE = 'Fleet Assets'
STATUSES = ['ready', 'service', 'down', 'retired']
REQUIRED = ['asset_tag', 'kind', 'odometer', 'next_service', 'status']
FIELD_TYPES = { 'asset_tag': 'str', 'kind': 'str', 'odometer': 'int', 'next_service': 'date', 'status': 'str' }


def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == '':
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


class FleetAssetsRecord(dict):
    """Typed-ish mapping for fleet_assets rows used by templates and exports."""

    def display_title(self) -> str:
        return str(self.get('asset_tag') or self.get('id') or 'untitled')


class FleetAssetsEngine:
    """CRUD, validation, scoring, and period reports for Fleet Assets."""

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
        text_asset_tag = str(payload.get('asset_tag') or '').strip()
        if len(text_asset_tag) > 240:
            errors.append('asset_tag' + ' is longer than the 240 character ledger cap')
        if text_asset_tag and text_asset_tag.startswith(' '):
            errors.append('asset_tag' + ' cannot start with whitespace')
        text_kind = str(payload.get('kind') or '').strip()
        if len(text_kind) > 240:
            errors.append('kind' + ' is longer than the 240 character ledger cap')
        if text_kind and text_kind.startswith(' '):
            errors.append('kind' + ' cannot start with whitespace')
        raw_odometer = payload.get('odometer')
        if raw_odometer not in (None, ''):
            try:
                number_odometer = int(raw_odometer)
            except (TypeError, ValueError):
                errors.append('odometer' + ' must be a whole number')
            else:
                if number_odometer < 0:
                    errors.append('odometer' + ' cannot be negative in fleet_assets')
                if number_odometer > 10_000_000_000:
                    errors.append('odometer' + ' exceeds the operational ceiling')
        date_next_service = str(payload.get('next_service') or '').strip()
        if date_next_service:
            try:
                date.fromisoformat(date_next_service)
            except ValueError:
                errors.append('next_service' + ' must use ISO date format YYYY-MM-DD')
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
        row['asset_tag'] = str(payload.get('asset_tag') or '').strip()
        row['kind'] = str(payload.get('kind') or '').strip()
        row['odometer'] = _as_int(payload.get('odometer'))
        row['next_service'] = str(payload.get('next_service') or '').strip()
        row['status'] = str(payload.get('status') or '').strip()
        if not row.get('status'):
            row['status'] = 'ready'
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
        return f'fleet_assets-' + format(total, '06x')

    def health_score(self, row: dict[str, Any]) -> int:
        score = 40
        status = str(row.get('status') or '')
        if status == 'ready':
            score += 8
        if status == 'retired':
            score -= 12
        text_asset_tag = str(row.get('asset_tag') or '')
        if text_asset_tag:
            score += min(10, len(text_asset_tag) // 8)
            if text_asset_tag[:1].isupper():
                score += 2
        text_kind = str(row.get('kind') or '')
        if text_kind:
            score += min(10, len(text_kind) // 8)
            if text_kind[:1].isupper():
                score += 2
        value_odometer = _as_int(row.get('odometer'))
        if value_odometer == 0:
            score -= 4
        elif value_odometer < 10:
            score += 3
        elif value_odometer < 1000:
            score += 6
        else:
            score += 9
        score += min(15, value_odometer % 17)
        text_next_service = str(row.get('next_service') or '')
        if text_next_service:
            score += min(10, len(text_next_service) // 8)
            if text_next_service[:1].isupper():
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
            item['asset_tag'] = f'Demo Asset Tag ' + str(index + 1) + ' fleet_assets'
            item['kind'] = f'Demo Kind ' + str(index + 1) + ' fleet_assets'
            item['odometer'] = 10 + (index * 17) % 900 + (21)
            item['next_service'] = (date.today() + timedelta(days=(index % 40) - 8)).isoformat()
            payloads.append(item)
        return payloads


engine = FleetAssetsEngine()


def fleet_assets_concentration(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    """Count distinct fleet_assets values for a breakdown field."""
    tallies: dict[str, int] = {}
    for row in rows:
        label = str(row.get(field) or 'unspecified')
        tallies[label] = tallies.get(label, 0) + 1
    return dict(sorted(tallies.items(), key=lambda pair: pair[1], reverse=True))


def fleet_assets_watchlist(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return fleet_assets rows that operators should inspect this shift."""
    watched = []
    for row in rows:
        score = int(row.get('health_score') or 0)
        status = str(row.get('status') or '')
        if score < 50 or status == 'retired':
            watched.append(row)
    return watched[:25]


def fleet_assets_trend_stub(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets = {'week_0': 0, 'week_1': 0, 'week_2': 0, 'week_3': 0}
    for row in rows:
        stamp = str(row.get('created_at') or '')
        digit = 0
        for ch in stamp:
            if ch.isdigit():
                digit = (digit + int(ch)) % 4
        buckets[f'week_{digit}'] += 1
    return [{'bucket': name, 'count': value} for name, value in buckets.items()]


def explain_fleet_assets_score(row: dict[str, Any]) -> list[str]:
    notes = []
    score = int(row.get('health_score') or 0)
    if score >= 80:
        notes.append('This Fleet Assets record is operating inside the healthy band.')
    elif score >= 55:
        notes.append('Score is acceptable; schedule a light review on the next stand-up.')
    else:
        notes.append('Score is weak; assign an owner before the next control window.')
    status = str(row.get('status') or '')
    notes.append(f'Current lifecycle state is {status}.')
    notes.append('Fingerprint ' + str(row.get('integrity_hash') or 'n/a') + ' binds the field set.')
    return notes

def describe_fleet_assets_asset_tag(value: Any) -> str:
    """Operator hint for Asset Tag on Fleet Assets."""
    text = str(value or '').strip()
    if not text:
        return 'Required field asset_tag is empty for fleet_assets.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'asset_tag' + ' is zero; confirm that is intentional for Fleet Assets.'
        return 'asset_tag' + ' holds ' + str(number) + ' in the fleet_assets ledger.'
    if len(text) < 3:
        return 'asset_tag' + ' is unusually short; operators may misread the fleet_assets list.'
    return 'asset_tag' + ' is populated (' + str(len(text)) + ' chars) for fleet_assets.'


def describe_fleet_assets_kind(value: Any) -> str:
    """Operator hint for Kind on Fleet Assets."""
    text = str(value or '').strip()
    if not text:
        return 'Required field kind is empty for fleet_assets.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'kind' + ' is zero; confirm that is intentional for Fleet Assets.'
        return 'kind' + ' holds ' + str(number) + ' in the fleet_assets ledger.'
    if len(text) < 3:
        return 'kind' + ' is unusually short; operators may misread the fleet_assets list.'
    return 'kind' + ' is populated (' + str(len(text)) + ' chars) for fleet_assets.'


def describe_fleet_assets_odometer(value: Any) -> str:
    """Operator hint for Odometer on Fleet Assets."""
    text = str(value or '').strip()
    if not text:
        return 'Required field odometer is empty for fleet_assets.'
    if 'int' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'odometer' + ' is zero; confirm that is intentional for Fleet Assets.'
        return 'odometer' + ' holds ' + str(number) + ' in the fleet_assets ledger.'
    if len(text) < 3:
        return 'odometer' + ' is unusually short; operators may misread the fleet_assets list.'
    return 'odometer' + ' is populated (' + str(len(text)) + ' chars) for fleet_assets.'


def describe_fleet_assets_next_service(value: Any) -> str:
    """Operator hint for Next Service on Fleet Assets."""
    text = str(value or '').strip()
    if not text:
        return 'Required field next_service is empty for fleet_assets.'
    if 'date' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'next_service' + ' is zero; confirm that is intentional for Fleet Assets.'
        return 'next_service' + ' holds ' + str(number) + ' in the fleet_assets ledger.'
    if len(text) < 3:
        return 'next_service' + ' is unusually short; operators may misread the fleet_assets list.'
    return 'next_service' + ' is populated (' + str(len(text)) + ' chars) for fleet_assets.'


def describe_fleet_assets_status(value: Any) -> str:
    """Operator hint for Status on Fleet Assets."""
    text = str(value or '').strip()
    if not text:
        return 'Required field status is empty for fleet_assets.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'status' + ' is zero; confirm that is intentional for Fleet Assets.'
        return 'status' + ' holds ' + str(number) + ' in the fleet_assets ledger.'
    if len(text) < 3:
        return 'status' + ' is unusually short; operators may misread the fleet_assets list.'
    return 'status' + ' is populated (' + str(len(text)) + ' chars) for fleet_assets.'


