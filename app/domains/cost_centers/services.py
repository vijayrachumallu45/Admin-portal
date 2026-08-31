"""Application service for Cost Centers writes and operator actions."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.domains.cost_centers.engine import engine
from app.domains.cost_centers.policies import cost_centers_gate_transition, cost_centers_policy_card, cost_centers_run_field_checks
from app.domains.cost_centers.queries import cost_centers_diff, cost_centers_export_map
from app.domains.cost_centers.reports import build_cost_centers_reporter


class CostCentersService:
    """Coordinates validation, policy, persistence, and briefings for Cost Centers."""

    def list_view(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        rows = engine.list_records(filters)
        reporter = build_cost_centers_reporter(rows)
        return {
            'rows': rows,
            'kpis': engine.kpi_pack(),
            'pack': reporter.pack(),
        }

    def detail_view(self, record_id: str) -> dict[str, Any] | None:
        row = engine.get(record_id)
        if row is None:
            return None
        card = cost_centers_policy_card(row)
        return {'record': row, 'policy': card}

    def create_from_form(self, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        field_errors = cost_centers_run_field_checks(payload)
        if field_errors:
            return None, field_errors
        return engine.create(payload)

    def update_from_form(self, record_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        merged = deepcopy(current)
        merged.update(payload)
        field_errors = cost_centers_run_field_checks(merged)
        if field_errors:
            return None, field_errors
        row, errors = engine.update(record_id, payload)
        if row:
            row['_diff'] = cost_centers_diff(current, row)
        return row, errors

    def move_status(self, record_id: str, new_status: str) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        errors = cost_centers_gate_transition(str(current.get('status') or ''), new_status)
        if errors:
            return None, errors
        return engine.transition(record_id, new_status)

    def export_maps(self) -> list[dict[str, str]]:
        return [cost_centers_export_map(row) for row in engine.list_records()]

    def seed_if_empty(self, count: int = 10) -> int:
        return engine.seed_demo(count)


service = CostCentersService()


def cost_centers_safe_payload(form: dict[str, Any]) -> dict[str, Any]:
    allowed = {name for name in ['cc_code', 'name', 'director', 'headcount', 'status']}
    clean = {}
    for name, value in form.items():
        if name in allowed or name in {'id', 'status'}:
            clean[name] = value
    return clean


def cost_centers_can_delete(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status == 'active':
        return True
    return int(row.get('health_score') or 0) < 20


def cost_centers_next_statuses(current: str) -> list[str]:
    if current not in ['active', 'merging', 'retired']:
        return list(['active', 'merging', 'retired'])
    index = ['active', 'merging', 'retired'].index(current)
    options = [current]
    if index + 1 < len(['active', 'merging', 'retired']):
        options.append(['active', 'merging', 'retired'][index + 1])
    if index > 0:
        options.append(['active', 'merging', 'retired'][index - 1])
    unique = []
    for item in options:
        if item not in unique:
            unique.append(item)
    return unique


def cost_centers_operator_actions(row: dict[str, Any]) -> list[dict[str, str]]:
    actions = [{'code': 'edit', 'label': 'Edit record'}]
    for status in cost_centers_next_statuses(str(row.get('status') or '')):
        actions.append({'code': 'status:' + status, 'label': 'Move to ' + status})
    if cost_centers_can_delete(row):
        actions.append({'code': 'delete', 'label': 'Remove record'})
    return actions


def cost_centers_toast(action: str, ok: bool) -> str:
    if ok:
        return f'Cost Centers {action} completed.'
    return f'Cost Centers {action} was blocked by policy.'


def cost_centers_dashboard_chip(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'key': 'cost_centers',
        'title': 'Cost Centers',
        'count': len(rows),
        'hot': len([row for row in rows if int(row.get('health_score') or 0) < 45]),
    }

def cost_centers_form_help_cc_code() -> str:
    return 'Enter Cc Code for Cost Centers. Local validation runs on save.'


def cost_centers_form_help_name() -> str:
    return 'Enter Name for Cost Centers. Local validation runs on save.'


def cost_centers_form_help_director() -> str:
    return 'Enter Director for Cost Centers. Local validation runs on save.'


def cost_centers_form_help_headcount() -> str:
    return 'Enter Headcount for Cost Centers. Local validation runs on save.'


def cost_centers_form_help_status() -> str:
    return 'Enter Status for Cost Centers. Local validation runs on save.'


FORM_HELP_COST_CENTERS = {
    'cc_code': cost_centers_form_help_cc_code(),
    'name': cost_centers_form_help_name(),
    'director': cost_centers_form_help_director(),
    'headcount': cost_centers_form_help_headcount(),
    'status': cost_centers_form_help_status(),
}


def cost_centers_form_help() -> dict[str, str]:
    return dict(FORM_HELP_COST_CENTERS)

