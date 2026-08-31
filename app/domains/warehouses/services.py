"""Application service for Warehouse Map writes and operator actions."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.domains.warehouses.engine import engine
from app.domains.warehouses.policies import warehouses_gate_transition, warehouses_policy_card, warehouses_run_field_checks
from app.domains.warehouses.queries import warehouses_diff, warehouses_export_map
from app.domains.warehouses.reports import build_warehouses_reporter


class WarehousesService:
    """Coordinates validation, policy, persistence, and briefings for Warehouse Map."""

    def list_view(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        rows = engine.list_records(filters)
        reporter = build_warehouses_reporter(rows)
        return {
            'rows': rows,
            'kpis': engine.kpi_pack(),
            'pack': reporter.pack(),
        }

    def detail_view(self, record_id: str) -> dict[str, Any] | None:
        row = engine.get(record_id)
        if row is None:
            return None
        card = warehouses_policy_card(row)
        return {'record': row, 'policy': card}

    def create_from_form(self, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        field_errors = warehouses_run_field_checks(payload)
        if field_errors:
            return None, field_errors
        return engine.create(payload)

    def update_from_form(self, record_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        merged = deepcopy(current)
        merged.update(payload)
        field_errors = warehouses_run_field_checks(merged)
        if field_errors:
            return None, field_errors
        row, errors = engine.update(record_id, payload)
        if row:
            row['_diff'] = warehouses_diff(current, row)
        return row, errors

    def move_status(self, record_id: str, new_status: str) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        errors = warehouses_gate_transition(str(current.get('status') or ''), new_status)
        if errors:
            return None, errors
        return engine.transition(record_id, new_status)

    def export_maps(self) -> list[dict[str, str]]:
        return [warehouses_export_map(row) for row in engine.list_records()]

    def seed_if_empty(self, count: int = 10) -> int:
        return engine.seed_demo(count)


service = WarehousesService()


def warehouses_safe_payload(form: dict[str, Any]) -> dict[str, Any]:
    allowed = {name for name in ['site_code', 'city', 'capacity_pallets', 'timezone', 'manager', 'status']}
    clean = {}
    for name, value in form.items():
        if name in allowed or name in {'id', 'status'}:
            clean[name] = value
    return clean


def warehouses_can_delete(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status == 'active':
        return True
    return int(row.get('health_score') or 0) < 20


def warehouses_next_statuses(current: str) -> list[str]:
    if current not in ['active', 'maintenance', 'closed']:
        return list(['active', 'maintenance', 'closed'])
    index = ['active', 'maintenance', 'closed'].index(current)
    options = [current]
    if index + 1 < len(['active', 'maintenance', 'closed']):
        options.append(['active', 'maintenance', 'closed'][index + 1])
    if index > 0:
        options.append(['active', 'maintenance', 'closed'][index - 1])
    unique = []
    for item in options:
        if item not in unique:
            unique.append(item)
    return unique


def warehouses_operator_actions(row: dict[str, Any]) -> list[dict[str, str]]:
    actions = [{'code': 'edit', 'label': 'Edit record'}]
    for status in warehouses_next_statuses(str(row.get('status') or '')):
        actions.append({'code': 'status:' + status, 'label': 'Move to ' + status})
    if warehouses_can_delete(row):
        actions.append({'code': 'delete', 'label': 'Remove record'})
    return actions


def warehouses_toast(action: str, ok: bool) -> str:
    if ok:
        return f'Warehouse Map {action} completed.'
    return f'Warehouse Map {action} was blocked by policy.'


def warehouses_dashboard_chip(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'key': 'warehouses',
        'title': 'Warehouse Map',
        'count': len(rows),
        'hot': len([row for row in rows if int(row.get('health_score') or 0) < 45]),
    }

def warehouses_form_help_site_code() -> str:
    return 'Enter Site Code for Warehouse Map. Local validation runs on save.'


def warehouses_form_help_city() -> str:
    return 'Enter City for Warehouse Map. Local validation runs on save.'


def warehouses_form_help_capacity_pallets() -> str:
    return 'Enter Capacity Pallets for Warehouse Map. Local validation runs on save.'


def warehouses_form_help_timezone() -> str:
    return 'Enter Timezone for Warehouse Map. Local validation runs on save.'


def warehouses_form_help_manager() -> str:
    return 'Enter Manager for Warehouse Map. Local validation runs on save.'


def warehouses_form_help_status() -> str:
    return 'Enter Status for Warehouse Map. Local validation runs on save.'


FORM_HELP_WAREHOUSES = {
    'site_code': warehouses_form_help_site_code(),
    'city': warehouses_form_help_city(),
    'capacity_pallets': warehouses_form_help_capacity_pallets(),
    'timezone': warehouses_form_help_timezone(),
    'manager': warehouses_form_help_manager(),
    'status': warehouses_form_help_status(),
}


def warehouses_form_help() -> dict[str, str]:
    return dict(FORM_HELP_WAREHOUSES)

