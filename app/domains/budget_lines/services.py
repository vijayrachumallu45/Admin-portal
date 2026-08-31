"""Application service for Budget Lines writes and operator actions."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.domains.budget_lines.engine import engine
from app.domains.budget_lines.policies import budget_lines_gate_transition, budget_lines_policy_card, budget_lines_run_field_checks
from app.domains.budget_lines.queries import budget_lines_diff, budget_lines_export_map
from app.domains.budget_lines.reports import build_budget_lines_reporter


class BudgetLinesService:
    """Coordinates validation, policy, persistence, and briefings for Budget Lines."""

    def list_view(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        rows = engine.list_records(filters)
        reporter = build_budget_lines_reporter(rows)
        return {
            'rows': rows,
            'kpis': engine.kpi_pack(),
            'pack': reporter.pack(),
        }

    def detail_view(self, record_id: str) -> dict[str, Any] | None:
        row = engine.get(record_id)
        if row is None:
            return None
        card = budget_lines_policy_card(row)
        return {'record': row, 'policy': card}

    def create_from_form(self, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        field_errors = budget_lines_run_field_checks(payload)
        if field_errors:
            return None, field_errors
        return engine.create(payload)

    def update_from_form(self, record_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        merged = deepcopy(current)
        merged.update(payload)
        field_errors = budget_lines_run_field_checks(merged)
        if field_errors:
            return None, field_errors
        row, errors = engine.update(record_id, payload)
        if row:
            row['_diff'] = budget_lines_diff(current, row)
        return row, errors

    def move_status(self, record_id: str, new_status: str) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        errors = budget_lines_gate_transition(str(current.get('status') or ''), new_status)
        if errors:
            return None, errors
        return engine.transition(record_id, new_status)

    def export_maps(self) -> list[dict[str, str]]:
        return [budget_lines_export_map(row) for row in engine.list_records()]

    def seed_if_empty(self, count: int = 10) -> int:
        return engine.seed_demo(count)


service = BudgetLinesService()


def budget_lines_safe_payload(form: dict[str, Any]) -> dict[str, Any]:
    allowed = {name for name in ['line_code', 'owner', 'annual_cents', 'spent_cents', 'status']}
    clean = {}
    for name, value in form.items():
        if name in allowed or name in {'id', 'status'}:
            clean[name] = value
    return clean


def budget_lines_can_delete(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status == 'open':
        return True
    return int(row.get('health_score') or 0) < 20


def budget_lines_next_statuses(current: str) -> list[str]:
    if current not in ['open', 'watch', 'frozen', 'closed']:
        return list(['open', 'watch', 'frozen', 'closed'])
    index = ['open', 'watch', 'frozen', 'closed'].index(current)
    options = [current]
    if index + 1 < len(['open', 'watch', 'frozen', 'closed']):
        options.append(['open', 'watch', 'frozen', 'closed'][index + 1])
    if index > 0:
        options.append(['open', 'watch', 'frozen', 'closed'][index - 1])
    unique = []
    for item in options:
        if item not in unique:
            unique.append(item)
    return unique


def budget_lines_operator_actions(row: dict[str, Any]) -> list[dict[str, str]]:
    actions = [{'code': 'edit', 'label': 'Edit record'}]
    for status in budget_lines_next_statuses(str(row.get('status') or '')):
        actions.append({'code': 'status:' + status, 'label': 'Move to ' + status})
    if budget_lines_can_delete(row):
        actions.append({'code': 'delete', 'label': 'Remove record'})
    return actions


def budget_lines_toast(action: str, ok: bool) -> str:
    if ok:
        return f'Budget Lines {action} completed.'
    return f'Budget Lines {action} was blocked by policy.'


def budget_lines_dashboard_chip(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'key': 'budget_lines',
        'title': 'Budget Lines',
        'count': len(rows),
        'hot': len([row for row in rows if int(row.get('health_score') or 0) < 45]),
    }

def budget_lines_form_help_line_code() -> str:
    return 'Enter Line Code for Budget Lines. Local validation runs on save.'


def budget_lines_form_help_owner() -> str:
    return 'Enter Owner for Budget Lines. Local validation runs on save.'


def budget_lines_form_help_annual_cents() -> str:
    return 'Enter Annual Cents for Budget Lines. Local validation runs on save.'


def budget_lines_form_help_spent_cents() -> str:
    return 'Enter Spent Cents for Budget Lines. Local validation runs on save.'


def budget_lines_form_help_status() -> str:
    return 'Enter Status for Budget Lines. Local validation runs on save.'


FORM_HELP_BUDGET_LINES = {
    'line_code': budget_lines_form_help_line_code(),
    'owner': budget_lines_form_help_owner(),
    'annual_cents': budget_lines_form_help_annual_cents(),
    'spent_cents': budget_lines_form_help_spent_cents(),
    'status': budget_lines_form_help_status(),
}


def budget_lines_form_help() -> dict[str, str]:
    return dict(FORM_HELP_BUDGET_LINES)

