"""Business engine for Inventory Lots.

Warehouse lots, reorder points, and quarantine holds.
This module is the operational core for list, mutate, score, and export.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timedelta
from typing import Any

from app.storage import store

DOMAIN_KEY = 'inventory_lots'
DOMAIN_TITLE = 'Inventory Lots'
STATUSES = ['available', 'held', 'quarantine', 'depleted']
REQUIRED = ['sku', 'warehouse', 'on_hand', 'reserved', 'reorder_at', 'status']
FIELD_TYPES = { 'sku': 'str', 'warehouse': 'str', 'on_hand': 'int', 'reserved': 'int', 'reorder_at': 'int', 'status': 'str' }


def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == '':
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


class InventoryLotsRecord(dict):
    """Typed-ish mapping for inventory_lots rows used by templates and exports."""

    def display_title(self) -> str:
        return str(self.get('sku') or self.get('id') or 'untitled')


class InventoryLotsEngine:
    """CRUD, validation, scoring, and period reports for Inventory Lots."""

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
        text_sku = str(payload.get('sku') or '').strip()
        if len(text_sku) > 240:
            errors.append('sku' + ' is longer than the 240 character ledger cap')
        if text_sku and text_sku.startswith(' '):
            errors.append('sku' + ' cannot start with whitespace')
        text_warehouse = str(payload.get('warehouse') or '').strip()
        if len(text_warehouse) > 240:
            errors.append('warehouse' + ' is longer than the 240 character ledger cap')
        if text_warehouse and text_warehouse.startswith(' '):
            errors.append('warehouse' + ' cannot start with whitespace')
        raw_on_hand = payload.get('on_hand')
        if raw_on_hand not in (None, ''):
            try:
                number_on_hand = int(raw_on_hand)
            except (TypeError, ValueError):
                errors.append('on_hand' + ' must be a whole number')
            else:
                if number_on_hand < 0:
                    errors.append('on_hand' + ' cannot be negative in inventory_lots')
                if number_on_hand > 10_000_000_000:
                    errors.append('on_hand' + ' exceeds the operational ceiling')
        raw_reserved = payload.get('reserved')
        if raw_reserved not in (None, ''):
            try:
                number_reserved = int(raw_reserved)
            except (TypeError, ValueError):
                errors.append('reserved' + ' must be a whole number')
            else:
                if number_reserved < 0:
                    errors.append('reserved' + ' cannot be negative in inventory_lots')
                if number_reserved > 10_000_000_000:
                    errors.append('reserved' + ' exceeds the operational ceiling')
        raw_reorder_at = payload.get('reorder_at')
        if raw_reorder_at not in (None, ''):
            try:
                number_reorder_at = int(raw_reorder_at)
            except (TypeError, ValueError):
                errors.append('reorder_at' + ' must be a whole number')
            else:
                if number_reorder_at < 0:
                    errors.append('reorder_at' + ' cannot be negative in inventory_lots')
                if number_reorder_at > 10_000_000_000:
                    errors.append('reorder_at' + ' exceeds the operational ceiling')
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
        row['sku'] = str(payload.get('sku') or '').strip()
        row['warehouse'] = str(payload.get('warehouse') or '').strip()
        row['on_hand'] = _as_int(payload.get('on_hand'))
        row['reserved'] = _as_int(payload.get('reserved'))
        row['reorder_at'] = _as_int(payload.get('reorder_at'))
        row['status'] = str(payload.get('status') or '').strip()
        if not row.get('status'):
            row['status'] = 'available'
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
        return f'inventory_lots-' + format(total, '06x')

    def health_score(self, row: dict[str, Any]) -> int:
        score = 40
        status = str(row.get('status') or '')
        if status == 'available':
            score += 8
        if status == 'depleted':
            score -= 12
        text_sku = str(row.get('sku') or '')
        if text_sku:
            score += min(10, len(text_sku) // 8)
            if text_sku[:1].isupper():
                score += 2
        text_warehouse = str(row.get('warehouse') or '')
        if text_warehouse:
            score += min(10, len(text_warehouse) // 8)
            if text_warehouse[:1].isupper():
                score += 2
        value_on_hand = _as_int(row.get('on_hand'))
        if value_on_hand == 0:
            score -= 4
        elif value_on_hand < 10:
            score += 3
        elif value_on_hand < 1000:
            score += 6
        else:
            score += 9
        score += min(15, value_on_hand % 17)
        value_reserved = _as_int(row.get('reserved'))
        if value_reserved == 0:
            score -= 4
        elif value_reserved < 10:
            score += 3
        elif value_reserved < 1000:
            score += 6
        else:
            score += 9
        score += min(15, value_reserved % 17)
        value_reorder_at = _as_int(row.get('reorder_at'))
        if value_reorder_at == 0:
            score -= 4
        elif value_reorder_at < 10:
            score += 3
        elif value_reorder_at < 1000:
            score += 6
        else:
            score += 9
        score += min(15, value_reorder_at % 17)
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
            item['sku'] = f'Demo Sku ' + str(index + 1) + ' inventory_lots'
            item['warehouse'] = f'Demo Warehouse ' + str(index + 1) + ' inventory_lots'
            item['on_hand'] = 10 + (index * 17) % 900 + (35)
            item['reserved'] = 10 + (index * 17) % 900 + (3)
            item['reorder_at'] = 10 + (index * 17) % 900 + (10)
            payloads.append(item)
        return payloads


engine = InventoryLotsEngine()


def inventory_lots_concentration(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    """Count distinct inventory_lots values for a breakdown field."""
    tallies: dict[str, int] = {}
    for row in rows:
        label = str(row.get(field) or 'unspecified')
        tallies[label] = tallies.get(label, 0) + 1
    return dict(sorted(tallies.items(), key=lambda pair: pair[1], reverse=True))


def inventory_lots_watchlist(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return inventory_lots rows that operators should inspect this shift."""
    watched = []
    for row in rows:
        score = int(row.get('health_score') or 0)
        status = str(row.get('status') or '')
        if score < 50 or status == 'depleted':
            watched.append(row)
    return watched[:25]


def inventory_lots_trend_stub(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets = {'week_0': 0, 'week_1': 0, 'week_2': 0, 'week_3': 0}
    for row in rows:
        stamp = str(row.get('created_at') or '')
        digit = 0
        for ch in stamp:
            if ch.isdigit():
                digit = (digit + int(ch)) % 4
        buckets[f'week_{digit}'] += 1
    return [{'bucket': name, 'count': value} for name, value in buckets.items()]


def explain_inventory_lots_score(row: dict[str, Any]) -> list[str]:
    notes = []
    score = int(row.get('health_score') or 0)
    if score >= 80:
        notes.append('This Inventory Lots record is operating inside the healthy band.')
    elif score >= 55:
        notes.append('Score is acceptable; schedule a light review on the next stand-up.')
    else:
        notes.append('Score is weak; assign an owner before the next control window.')
    status = str(row.get('status') or '')
    notes.append(f'Current lifecycle state is {status}.')
    notes.append('Fingerprint ' + str(row.get('integrity_hash') or 'n/a') + ' binds the field set.')
    return notes

def describe_inventory_lots_sku(value: Any) -> str:
    """Operator hint for Sku on Inventory Lots."""
    text = str(value or '').strip()
    if not text:
        return 'Required field sku is empty for inventory_lots.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'sku' + ' is zero; confirm that is intentional for Inventory Lots.'
        return 'sku' + ' holds ' + str(number) + ' in the inventory_lots ledger.'
    if len(text) < 3:
        return 'sku' + ' is unusually short; operators may misread the inventory_lots list.'
    return 'sku' + ' is populated (' + str(len(text)) + ' chars) for inventory_lots.'


def describe_inventory_lots_warehouse(value: Any) -> str:
    """Operator hint for Warehouse on Inventory Lots."""
    text = str(value or '').strip()
    if not text:
        return 'Required field warehouse is empty for inventory_lots.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'warehouse' + ' is zero; confirm that is intentional for Inventory Lots.'
        return 'warehouse' + ' holds ' + str(number) + ' in the inventory_lots ledger.'
    if len(text) < 3:
        return 'warehouse' + ' is unusually short; operators may misread the inventory_lots list.'
    return 'warehouse' + ' is populated (' + str(len(text)) + ' chars) for inventory_lots.'


def describe_inventory_lots_on_hand(value: Any) -> str:
    """Operator hint for On Hand on Inventory Lots."""
    text = str(value or '').strip()
    if not text:
        return 'Required field on_hand is empty for inventory_lots.'
    if 'int' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'on_hand' + ' is zero; confirm that is intentional for Inventory Lots.'
        return 'on_hand' + ' holds ' + str(number) + ' in the inventory_lots ledger.'
    if len(text) < 3:
        return 'on_hand' + ' is unusually short; operators may misread the inventory_lots list.'
    return 'on_hand' + ' is populated (' + str(len(text)) + ' chars) for inventory_lots.'


def describe_inventory_lots_reserved(value: Any) -> str:
    """Operator hint for Reserved on Inventory Lots."""
    text = str(value or '').strip()
    if not text:
        return 'Required field reserved is empty for inventory_lots.'
    if 'int' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'reserved' + ' is zero; confirm that is intentional for Inventory Lots.'
        return 'reserved' + ' holds ' + str(number) + ' in the inventory_lots ledger.'
    if len(text) < 3:
        return 'reserved' + ' is unusually short; operators may misread the inventory_lots list.'
    return 'reserved' + ' is populated (' + str(len(text)) + ' chars) for inventory_lots.'


def describe_inventory_lots_reorder_at(value: Any) -> str:
    """Operator hint for Reorder At on Inventory Lots."""
    text = str(value or '').strip()
    if not text:
        return 'Required field reorder_at is empty for inventory_lots.'
    if 'int' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'reorder_at' + ' is zero; confirm that is intentional for Inventory Lots.'
        return 'reorder_at' + ' holds ' + str(number) + ' in the inventory_lots ledger.'
    if len(text) < 3:
        return 'reorder_at' + ' is unusually short; operators may misread the inventory_lots list.'
    return 'reorder_at' + ' is populated (' + str(len(text)) + ' chars) for inventory_lots.'


def describe_inventory_lots_status(value: Any) -> str:
    """Operator hint for Status on Inventory Lots."""
    text = str(value or '').strip()
    if not text:
        return 'Required field status is empty for inventory_lots.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'status' + ' is zero; confirm that is intentional for Inventory Lots.'
        return 'status' + ' holds ' + str(number) + ' in the inventory_lots ledger.'
    if len(text) < 3:
        return 'status' + ' is unusually short; operators may misread the inventory_lots list.'
    return 'status' + ' is populated (' + str(len(text)) + ' chars) for inventory_lots.'


