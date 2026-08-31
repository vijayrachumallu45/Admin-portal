"""Application service for Inventory Lots writes and operator actions."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.domains.inventory_lots.engine import engine
from app.domains.inventory_lots.policies import inventory_lots_gate_transition, inventory_lots_policy_card, inventory_lots_run_field_checks
from app.domains.inventory_lots.queries import inventory_lots_diff, inventory_lots_export_map
from app.domains.inventory_lots.reports import build_inventory_lots_reporter


class InventoryLotsService:
    """Coordinates validation, policy, persistence, and briefings for Inventory Lots."""

    def list_view(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        rows = engine.list_records(filters)
        reporter = build_inventory_lots_reporter(rows)
        return {
            'rows': rows,
            'kpis': engine.kpi_pack(),
            'pack': reporter.pack(),
        }

    def detail_view(self, record_id: str) -> dict[str, Any] | None:
        row = engine.get(record_id)
        if row is None:
            return None
        card = inventory_lots_policy_card(row)
        return {'record': row, 'policy': card}

    def create_from_form(self, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        field_errors = inventory_lots_run_field_checks(payload)
        if field_errors:
            return None, field_errors
        return engine.create(payload)

    def update_from_form(self, record_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        merged = deepcopy(current)
        merged.update(payload)
        field_errors = inventory_lots_run_field_checks(merged)
        if field_errors:
            return None, field_errors
        row, errors = engine.update(record_id, payload)
        if row:
            row['_diff'] = inventory_lots_diff(current, row)
        return row, errors

    def move_status(self, record_id: str, new_status: str) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        errors = inventory_lots_gate_transition(str(current.get('status') or ''), new_status)
        if errors:
            return None, errors
        return engine.transition(record_id, new_status)

    def export_maps(self) -> list[dict[str, str]]:
        return [inventory_lots_export_map(row) for row in engine.list_records()]

    def seed_if_empty(self, count: int = 10) -> int:
        return engine.seed_demo(count)


service = InventoryLotsService()


def inventory_lots_safe_payload(form: dict[str, Any]) -> dict[str, Any]:
    allowed = {name for name in ['sku', 'warehouse', 'on_hand', 'reserved', 'reorder_at', 'status']}
    clean = {}
    for name, value in form.items():
        if name in allowed or name in {'id', 'status'}:
            clean[name] = value
    return clean


def inventory_lots_can_delete(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status == 'available':
        return True
    return int(row.get('health_score') or 0) < 20


def inventory_lots_next_statuses(current: str) -> list[str]:
    if current not in ['available', 'held', 'quarantine', 'depleted']:
        return list(['available', 'held', 'quarantine', 'depleted'])
    index = ['available', 'held', 'quarantine', 'depleted'].index(current)
    options = [current]
    if index + 1 < len(['available', 'held', 'quarantine', 'depleted']):
        options.append(['available', 'held', 'quarantine', 'depleted'][index + 1])
    if index > 0:
        options.append(['available', 'held', 'quarantine', 'depleted'][index - 1])
    unique = []
    for item in options:
        if item not in unique:
            unique.append(item)
    return unique


def inventory_lots_operator_actions(row: dict[str, Any]) -> list[dict[str, str]]:
    actions = [{'code': 'edit', 'label': 'Edit record'}]
    for status in inventory_lots_next_statuses(str(row.get('status') or '')):
        actions.append({'code': 'status:' + status, 'label': 'Move to ' + status})
    if inventory_lots_can_delete(row):
        actions.append({'code': 'delete', 'label': 'Remove record'})
    return actions


def inventory_lots_toast(action: str, ok: bool) -> str:
    if ok:
        return f'Inventory Lots {action} completed.'
    return f'Inventory Lots {action} was blocked by policy.'


def inventory_lots_dashboard_chip(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'key': 'inventory_lots',
        'title': 'Inventory Lots',
        'count': len(rows),
        'hot': len([row for row in rows if int(row.get('health_score') or 0) < 45]),
    }

def inventory_lots_form_help_sku() -> str:
    return 'Enter Sku for Inventory Lots. Local validation runs on save.'


def inventory_lots_form_help_warehouse() -> str:
    return 'Enter Warehouse for Inventory Lots. Local validation runs on save.'


def inventory_lots_form_help_on_hand() -> str:
    return 'Enter On Hand for Inventory Lots. Local validation runs on save.'


def inventory_lots_form_help_reserved() -> str:
    return 'Enter Reserved for Inventory Lots. Local validation runs on save.'


def inventory_lots_form_help_reorder_at() -> str:
    return 'Enter Reorder At for Inventory Lots. Local validation runs on save.'


def inventory_lots_form_help_status() -> str:
    return 'Enter Status for Inventory Lots. Local validation runs on save.'


FORM_HELP_INVENTORY_LOTS = {
    'sku': inventory_lots_form_help_sku(),
    'warehouse': inventory_lots_form_help_warehouse(),
    'on_hand': inventory_lots_form_help_on_hand(),
    'reserved': inventory_lots_form_help_reserved(),
    'reorder_at': inventory_lots_form_help_reorder_at(),
    'status': inventory_lots_form_help_status(),
}


def inventory_lots_form_help() -> dict[str, str]:
    return dict(FORM_HELP_INVENTORY_LOTS)

