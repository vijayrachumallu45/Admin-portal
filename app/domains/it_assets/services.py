"""Application service for IT Asset Register writes and operator actions."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.domains.it_assets.engine import engine
from app.domains.it_assets.policies import it_assets_gate_transition, it_assets_policy_card, it_assets_run_field_checks
from app.domains.it_assets.queries import it_assets_diff, it_assets_export_map
from app.domains.it_assets.reports import build_it_assets_reporter


class ItAssetsService:
    """Coordinates validation, policy, persistence, and briefings for IT Asset Register."""

    def list_view(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        rows = engine.list_records(filters)
        reporter = build_it_assets_reporter(rows)
        return {
            'rows': rows,
            'kpis': engine.kpi_pack(),
            'pack': reporter.pack(),
        }

    def detail_view(self, record_id: str) -> dict[str, Any] | None:
        row = engine.get(record_id)
        if row is None:
            return None
        card = it_assets_policy_card(row)
        return {'record': row, 'policy': card}

    def create_from_form(self, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        field_errors = it_assets_run_field_checks(payload)
        if field_errors:
            return None, field_errors
        return engine.create(payload)

    def update_from_form(self, record_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        merged = deepcopy(current)
        merged.update(payload)
        field_errors = it_assets_run_field_checks(merged)
        if field_errors:
            return None, field_errors
        row, errors = engine.update(record_id, payload)
        if row:
            row['_diff'] = it_assets_diff(current, row)
        return row, errors

    def move_status(self, record_id: str, new_status: str) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        errors = it_assets_gate_transition(str(current.get('status') or ''), new_status)
        if errors:
            return None, errors
        return engine.transition(record_id, new_status)

    def export_maps(self) -> list[dict[str, str]]:
        return [it_assets_export_map(row) for row in engine.list_records()]

    def seed_if_empty(self, count: int = 10) -> int:
        return engine.seed_demo(count)


service = ItAssetsService()


def it_assets_safe_payload(form: dict[str, Any]) -> dict[str, Any]:
    allowed = {name for name in ['asset_tag', 'model_name', 'custodian', 'warranty_on', 'status']}
    clean = {}
    for name, value in form.items():
        if name in allowed or name in {'id', 'status'}:
            clean[name] = value
    return clean


def it_assets_can_delete(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status == 'stock':
        return True
    return int(row.get('health_score') or 0) < 20


def it_assets_next_statuses(current: str) -> list[str]:
    if current not in ['stock', 'assigned', 'repair', 'retired']:
        return list(['stock', 'assigned', 'repair', 'retired'])
    index = ['stock', 'assigned', 'repair', 'retired'].index(current)
    options = [current]
    if index + 1 < len(['stock', 'assigned', 'repair', 'retired']):
        options.append(['stock', 'assigned', 'repair', 'retired'][index + 1])
    if index > 0:
        options.append(['stock', 'assigned', 'repair', 'retired'][index - 1])
    unique = []
    for item in options:
        if item not in unique:
            unique.append(item)
    return unique


def it_assets_operator_actions(row: dict[str, Any]) -> list[dict[str, str]]:
    actions = [{'code': 'edit', 'label': 'Edit record'}]
    for status in it_assets_next_statuses(str(row.get('status') or '')):
        actions.append({'code': 'status:' + status, 'label': 'Move to ' + status})
    if it_assets_can_delete(row):
        actions.append({'code': 'delete', 'label': 'Remove record'})
    return actions


def it_assets_toast(action: str, ok: bool) -> str:
    if ok:
        return f'IT Asset Register {action} completed.'
    return f'IT Asset Register {action} was blocked by policy.'


def it_assets_dashboard_chip(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'key': 'it_assets',
        'title': 'IT Asset Register',
        'count': len(rows),
        'hot': len([row for row in rows if int(row.get('health_score') or 0) < 45]),
    }

def it_assets_form_help_asset_tag() -> str:
    return 'Enter Asset Tag for IT Asset Register. Local validation runs on save.'


def it_assets_form_help_model_name() -> str:
    return 'Enter Model Name for IT Asset Register. Local validation runs on save.'


def it_assets_form_help_custodian() -> str:
    return 'Enter Custodian for IT Asset Register. Local validation runs on save.'


def it_assets_form_help_warranty_on() -> str:
    return 'Enter Warranty On for IT Asset Register. Local validation runs on save.'


def it_assets_form_help_status() -> str:
    return 'Enter Status for IT Asset Register. Local validation runs on save.'


FORM_HELP_IT_ASSETS = {
    'asset_tag': it_assets_form_help_asset_tag(),
    'model_name': it_assets_form_help_model_name(),
    'custodian': it_assets_form_help_custodian(),
    'warranty_on': it_assets_form_help_warranty_on(),
    'status': it_assets_form_help_status(),
}


def it_assets_form_help() -> dict[str, str]:
    return dict(FORM_HELP_IT_ASSETS)

