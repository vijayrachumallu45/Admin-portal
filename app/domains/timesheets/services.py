"""Application service for Timesheets writes and operator actions."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.domains.timesheets.engine import engine
from app.domains.timesheets.policies import timesheets_gate_transition, timesheets_policy_card, timesheets_run_field_checks
from app.domains.timesheets.queries import timesheets_diff, timesheets_export_map
from app.domains.timesheets.reports import build_timesheets_reporter


class TimesheetsService:
    """Coordinates validation, policy, persistence, and briefings for Timesheets."""

    def list_view(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        rows = engine.list_records(filters)
        reporter = build_timesheets_reporter(rows)
        return {
            'rows': rows,
            'kpis': engine.kpi_pack(),
            'pack': reporter.pack(),
        }

    def detail_view(self, record_id: str) -> dict[str, Any] | None:
        row = engine.get(record_id)
        if row is None:
            return None
        card = timesheets_policy_card(row)
        return {'record': row, 'policy': card}

    def create_from_form(self, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        field_errors = timesheets_run_field_checks(payload)
        if field_errors:
            return None, field_errors
        return engine.create(payload)

    def update_from_form(self, record_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        merged = deepcopy(current)
        merged.update(payload)
        field_errors = timesheets_run_field_checks(merged)
        if field_errors:
            return None, field_errors
        row, errors = engine.update(record_id, payload)
        if row:
            row['_diff'] = timesheets_diff(current, row)
        return row, errors

    def move_status(self, record_id: str, new_status: str) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        errors = timesheets_gate_transition(str(current.get('status') or ''), new_status)
        if errors:
            return None, errors
        return engine.transition(record_id, new_status)

    def export_maps(self) -> list[dict[str, str]]:
        return [timesheets_export_map(row) for row in engine.list_records()]

    def seed_if_empty(self, count: int = 10) -> int:
        return engine.seed_demo(count)


service = TimesheetsService()


def timesheets_safe_payload(form: dict[str, Any]) -> dict[str, Any]:
    allowed = {name for name in ['employee_no', 'week_start', 'project_code', 'minutes', 'billable', 'status']}
    clean = {}
    for name, value in form.items():
        if name in allowed or name in {'id', 'status'}:
            clean[name] = value
    return clean


def timesheets_can_delete(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status == 'draft':
        return True
    return int(row.get('health_score') or 0) < 20


def timesheets_next_statuses(current: str) -> list[str]:
    if current not in ['draft', 'submitted', 'approved', 'locked']:
        return list(['draft', 'submitted', 'approved', 'locked'])
    index = ['draft', 'submitted', 'approved', 'locked'].index(current)
    options = [current]
    if index + 1 < len(['draft', 'submitted', 'approved', 'locked']):
        options.append(['draft', 'submitted', 'approved', 'locked'][index + 1])
    if index > 0:
        options.append(['draft', 'submitted', 'approved', 'locked'][index - 1])
    unique = []
    for item in options:
        if item not in unique:
            unique.append(item)
    return unique


def timesheets_operator_actions(row: dict[str, Any]) -> list[dict[str, str]]:
    actions = [{'code': 'edit', 'label': 'Edit record'}]
    for status in timesheets_next_statuses(str(row.get('status') or '')):
        actions.append({'code': 'status:' + status, 'label': 'Move to ' + status})
    if timesheets_can_delete(row):
        actions.append({'code': 'delete', 'label': 'Remove record'})
    return actions


def timesheets_toast(action: str, ok: bool) -> str:
    if ok:
        return f'Timesheets {action} completed.'
    return f'Timesheets {action} was blocked by policy.'


def timesheets_dashboard_chip(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'key': 'timesheets',
        'title': 'Timesheets',
        'count': len(rows),
        'hot': len([row for row in rows if int(row.get('health_score') or 0) < 45]),
    }

def timesheets_form_help_employee_no() -> str:
    return 'Enter Employee No for Timesheets. Local validation runs on save.'


def timesheets_form_help_week_start() -> str:
    return 'Enter Week Start for Timesheets. Local validation runs on save.'


def timesheets_form_help_project_code() -> str:
    return 'Enter Project Code for Timesheets. Local validation runs on save.'


def timesheets_form_help_minutes() -> str:
    return 'Enter Minutes for Timesheets. Local validation runs on save.'


def timesheets_form_help_billable() -> str:
    return 'Enter Billable for Timesheets. Local validation runs on save.'


def timesheets_form_help_status() -> str:
    return 'Enter Status for Timesheets. Local validation runs on save.'


FORM_HELP_TIMESHEETS = {
    'employee_no': timesheets_form_help_employee_no(),
    'week_start': timesheets_form_help_week_start(),
    'project_code': timesheets_form_help_project_code(),
    'minutes': timesheets_form_help_minutes(),
    'billable': timesheets_form_help_billable(),
    'status': timesheets_form_help_status(),
}


def timesheets_form_help() -> dict[str, str]:
    return dict(FORM_HELP_TIMESHEETS)

