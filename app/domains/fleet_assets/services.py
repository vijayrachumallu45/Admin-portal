"""Application service for Fleet Assets writes and operator actions."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.domains.fleet_assets.engine import engine
from app.domains.fleet_assets.policies import fleet_assets_gate_transition, fleet_assets_policy_card, fleet_assets_run_field_checks
from app.domains.fleet_assets.queries import fleet_assets_diff, fleet_assets_export_map
from app.domains.fleet_assets.reports import build_fleet_assets_reporter


class FleetAssetsService:
    """Coordinates validation, policy, persistence, and briefings for Fleet Assets."""

    def list_view(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        rows = engine.list_records(filters)
        reporter = build_fleet_assets_reporter(rows)
        return {
            'rows': rows,
            'kpis': engine.kpi_pack(),
            'pack': reporter.pack(),
        }

    def detail_view(self, record_id: str) -> dict[str, Any] | None:
        row = engine.get(record_id)
        if row is None:
            return None
        card = fleet_assets_policy_card(row)
        return {'record': row, 'policy': card}

    def create_from_form(self, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        field_errors = fleet_assets_run_field_checks(payload)
        if field_errors:
            return None, field_errors
        return engine.create(payload)

    def update_from_form(self, record_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        merged = deepcopy(current)
        merged.update(payload)
        field_errors = fleet_assets_run_field_checks(merged)
        if field_errors:
            return None, field_errors
        row, errors = engine.update(record_id, payload)
        if row:
            row['_diff'] = fleet_assets_diff(current, row)
        return row, errors

    def move_status(self, record_id: str, new_status: str) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        errors = fleet_assets_gate_transition(str(current.get('status') or ''), new_status)
        if errors:
            return None, errors
        return engine.transition(record_id, new_status)

    def export_maps(self) -> list[dict[str, str]]:
        return [fleet_assets_export_map(row) for row in engine.list_records()]

    def seed_if_empty(self, count: int = 10) -> int:
        return engine.seed_demo(count)


service = FleetAssetsService()


def fleet_assets_safe_payload(form: dict[str, Any]) -> dict[str, Any]:
    allowed = {name for name in ['asset_tag', 'kind', 'odometer', 'next_service', 'status']}
    clean = {}
    for name, value in form.items():
        if name in allowed or name in {'id', 'status'}:
            clean[name] = value
    return clean


def fleet_assets_can_delete(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status == 'ready':
        return True
    return int(row.get('health_score') or 0) < 20


def fleet_assets_next_statuses(current: str) -> list[str]:
    if current not in ['ready', 'service', 'down', 'retired']:
        return list(['ready', 'service', 'down', 'retired'])
    index = ['ready', 'service', 'down', 'retired'].index(current)
    options = [current]
    if index + 1 < len(['ready', 'service', 'down', 'retired']):
        options.append(['ready', 'service', 'down', 'retired'][index + 1])
    if index > 0:
        options.append(['ready', 'service', 'down', 'retired'][index - 1])
    unique = []
    for item in options:
        if item not in unique:
            unique.append(item)
    return unique


def fleet_assets_operator_actions(row: dict[str, Any]) -> list[dict[str, str]]:
    actions = [{'code': 'edit', 'label': 'Edit record'}]
    for status in fleet_assets_next_statuses(str(row.get('status') or '')):
        actions.append({'code': 'status:' + status, 'label': 'Move to ' + status})
    if fleet_assets_can_delete(row):
        actions.append({'code': 'delete', 'label': 'Remove record'})
    return actions


def fleet_assets_toast(action: str, ok: bool) -> str:
    if ok:
        return f'Fleet Assets {action} completed.'
    return f'Fleet Assets {action} was blocked by policy.'


def fleet_assets_dashboard_chip(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'key': 'fleet_assets',
        'title': 'Fleet Assets',
        'count': len(rows),
        'hot': len([row for row in rows if int(row.get('health_score') or 0) < 45]),
    }

def fleet_assets_form_help_asset_tag() -> str:
    return 'Enter Asset Tag for Fleet Assets. Local validation runs on save.'


def fleet_assets_form_help_kind() -> str:
    return 'Enter Kind for Fleet Assets. Local validation runs on save.'


def fleet_assets_form_help_odometer() -> str:
    return 'Enter Odometer for Fleet Assets. Local validation runs on save.'


def fleet_assets_form_help_next_service() -> str:
    return 'Enter Next Service for Fleet Assets. Local validation runs on save.'


def fleet_assets_form_help_status() -> str:
    return 'Enter Status for Fleet Assets. Local validation runs on save.'


FORM_HELP_FLEET_ASSETS = {
    'asset_tag': fleet_assets_form_help_asset_tag(),
    'kind': fleet_assets_form_help_kind(),
    'odometer': fleet_assets_form_help_odometer(),
    'next_service': fleet_assets_form_help_next_service(),
    'status': fleet_assets_form_help_status(),
}


def fleet_assets_form_help() -> dict[str, str]:
    return dict(FORM_HELP_FLEET_ASSETS)

