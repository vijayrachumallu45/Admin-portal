"""Application service for Data Catalog writes and operator actions."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.domains.data_assets.engine import engine
from app.domains.data_assets.policies import data_assets_gate_transition, data_assets_policy_card, data_assets_run_field_checks
from app.domains.data_assets.queries import data_assets_diff, data_assets_export_map
from app.domains.data_assets.reports import build_data_assets_reporter


class DataAssetsService:
    """Coordinates validation, policy, persistence, and briefings for Data Catalog."""

    def list_view(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        rows = engine.list_records(filters)
        reporter = build_data_assets_reporter(rows)
        return {
            'rows': rows,
            'kpis': engine.kpi_pack(),
            'pack': reporter.pack(),
        }

    def detail_view(self, record_id: str) -> dict[str, Any] | None:
        row = engine.get(record_id)
        if row is None:
            return None
        card = data_assets_policy_card(row)
        return {'record': row, 'policy': card}

    def create_from_form(self, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        field_errors = data_assets_run_field_checks(payload)
        if field_errors:
            return None, field_errors
        return engine.create(payload)

    def update_from_form(self, record_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        merged = deepcopy(current)
        merged.update(payload)
        field_errors = data_assets_run_field_checks(merged)
        if field_errors:
            return None, field_errors
        row, errors = engine.update(record_id, payload)
        if row:
            row['_diff'] = data_assets_diff(current, row)
        return row, errors

    def move_status(self, record_id: str, new_status: str) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        errors = data_assets_gate_transition(str(current.get('status') or ''), new_status)
        if errors:
            return None, errors
        return engine.transition(record_id, new_status)

    def export_maps(self) -> list[dict[str, str]]:
        return [data_assets_export_map(row) for row in engine.list_records()]

    def seed_if_empty(self, count: int = 10) -> int:
        return engine.seed_demo(count)


service = DataAssetsService()


def data_assets_safe_payload(form: dict[str, Any]) -> dict[str, Any]:
    allowed = {name for name in ['asset_key', 'system_name', 'classification', 'steward', 'status']}
    clean = {}
    for name, value in form.items():
        if name in allowed or name in {'id', 'status'}:
            clean[name] = value
    return clean


def data_assets_can_delete(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status == 'candidate':
        return True
    return int(row.get('health_score') or 0) < 20


def data_assets_next_statuses(current: str) -> list[str]:
    if current not in ['candidate', 'certified', 'restricted', 'archived']:
        return list(['candidate', 'certified', 'restricted', 'archived'])
    index = ['candidate', 'certified', 'restricted', 'archived'].index(current)
    options = [current]
    if index + 1 < len(['candidate', 'certified', 'restricted', 'archived']):
        options.append(['candidate', 'certified', 'restricted', 'archived'][index + 1])
    if index > 0:
        options.append(['candidate', 'certified', 'restricted', 'archived'][index - 1])
    unique = []
    for item in options:
        if item not in unique:
            unique.append(item)
    return unique


def data_assets_operator_actions(row: dict[str, Any]) -> list[dict[str, str]]:
    actions = [{'code': 'edit', 'label': 'Edit record'}]
    for status in data_assets_next_statuses(str(row.get('status') or '')):
        actions.append({'code': 'status:' + status, 'label': 'Move to ' + status})
    if data_assets_can_delete(row):
        actions.append({'code': 'delete', 'label': 'Remove record'})
    return actions


def data_assets_toast(action: str, ok: bool) -> str:
    if ok:
        return f'Data Catalog {action} completed.'
    return f'Data Catalog {action} was blocked by policy.'


def data_assets_dashboard_chip(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'key': 'data_assets',
        'title': 'Data Catalog',
        'count': len(rows),
        'hot': len([row for row in rows if int(row.get('health_score') or 0) < 45]),
    }

def data_assets_form_help_asset_key() -> str:
    return 'Enter Asset Key for Data Catalog. Local validation runs on save.'


def data_assets_form_help_system_name() -> str:
    return 'Enter System Name for Data Catalog. Local validation runs on save.'


def data_assets_form_help_classification() -> str:
    return 'Enter Classification for Data Catalog. Local validation runs on save.'


def data_assets_form_help_steward() -> str:
    return 'Enter Steward for Data Catalog. Local validation runs on save.'


def data_assets_form_help_status() -> str:
    return 'Enter Status for Data Catalog. Local validation runs on save.'


FORM_HELP_DATA_ASSETS = {
    'asset_key': data_assets_form_help_asset_key(),
    'system_name': data_assets_form_help_system_name(),
    'classification': data_assets_form_help_classification(),
    'steward': data_assets_form_help_steward(),
    'status': data_assets_form_help_status(),
}


def data_assets_form_help() -> dict[str, str]:
    return dict(FORM_HELP_DATA_ASSETS)

