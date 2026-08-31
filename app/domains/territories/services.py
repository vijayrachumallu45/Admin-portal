"""Application service for Sales Territories writes and operator actions."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.domains.territories.engine import engine
from app.domains.territories.policies import territories_gate_transition, territories_policy_card, territories_run_field_checks
from app.domains.territories.queries import territories_diff, territories_export_map
from app.domains.territories.reports import build_territories_reporter


class TerritoriesService:
    """Coordinates validation, policy, persistence, and briefings for Sales Territories."""

    def list_view(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        rows = engine.list_records(filters)
        reporter = build_territories_reporter(rows)
        return {
            'rows': rows,
            'kpis': engine.kpi_pack(),
            'pack': reporter.pack(),
        }

    def detail_view(self, record_id: str) -> dict[str, Any] | None:
        row = engine.get(record_id)
        if row is None:
            return None
        card = territories_policy_card(row)
        return {'record': row, 'policy': card}

    def create_from_form(self, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        field_errors = territories_run_field_checks(payload)
        if field_errors:
            return None, field_errors
        return engine.create(payload)

    def update_from_form(self, record_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        merged = deepcopy(current)
        merged.update(payload)
        field_errors = territories_run_field_checks(merged)
        if field_errors:
            return None, field_errors
        row, errors = engine.update(record_id, payload)
        if row:
            row['_diff'] = territories_diff(current, row)
        return row, errors

    def move_status(self, record_id: str, new_status: str) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        errors = territories_gate_transition(str(current.get('status') or ''), new_status)
        if errors:
            return None, errors
        return engine.transition(record_id, new_status)

    def export_maps(self) -> list[dict[str, str]]:
        return [territories_export_map(row) for row in engine.list_records()]

    def seed_if_empty(self, count: int = 10) -> int:
        return engine.seed_demo(count)


service = TerritoriesService()


def territories_safe_payload(form: dict[str, Any]) -> dict[str, Any]:
    allowed = {name for name in ['territory_code', 'name', 'owner', 'quota_cents', 'status']}
    clean = {}
    for name, value in form.items():
        if name in allowed or name in {'id', 'status'}:
            clean[name] = value
    return clean


def territories_can_delete(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status == 'open':
        return True
    return int(row.get('health_score') or 0) < 20


def territories_next_statuses(current: str) -> list[str]:
    if current not in ['open', 'covered', 'split']:
        return list(['open', 'covered', 'split'])
    index = ['open', 'covered', 'split'].index(current)
    options = [current]
    if index + 1 < len(['open', 'covered', 'split']):
        options.append(['open', 'covered', 'split'][index + 1])
    if index > 0:
        options.append(['open', 'covered', 'split'][index - 1])
    unique = []
    for item in options:
        if item not in unique:
            unique.append(item)
    return unique


def territories_operator_actions(row: dict[str, Any]) -> list[dict[str, str]]:
    actions = [{'code': 'edit', 'label': 'Edit record'}]
    for status in territories_next_statuses(str(row.get('status') or '')):
        actions.append({'code': 'status:' + status, 'label': 'Move to ' + status})
    if territories_can_delete(row):
        actions.append({'code': 'delete', 'label': 'Remove record'})
    return actions


def territories_toast(action: str, ok: bool) -> str:
    if ok:
        return f'Sales Territories {action} completed.'
    return f'Sales Territories {action} was blocked by policy.'


def territories_dashboard_chip(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'key': 'territories',
        'title': 'Sales Territories',
        'count': len(rows),
        'hot': len([row for row in rows if int(row.get('health_score') or 0) < 45]),
    }

def territories_form_help_territory_code() -> str:
    return 'Enter Territory Code for Sales Territories. Local validation runs on save.'


def territories_form_help_name() -> str:
    return 'Enter Name for Sales Territories. Local validation runs on save.'


def territories_form_help_owner() -> str:
    return 'Enter Owner for Sales Territories. Local validation runs on save.'


def territories_form_help_quota_cents() -> str:
    return 'Enter Quota Cents for Sales Territories. Local validation runs on save.'


def territories_form_help_status() -> str:
    return 'Enter Status for Sales Territories. Local validation runs on save.'


FORM_HELP_TERRITORIES = {
    'territory_code': territories_form_help_territory_code(),
    'name': territories_form_help_name(),
    'owner': territories_form_help_owner(),
    'quota_cents': territories_form_help_quota_cents(),
    'status': territories_form_help_status(),
}


def territories_form_help() -> dict[str, str]:
    return dict(FORM_HELP_TERRITORIES)

