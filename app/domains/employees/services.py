"""Application service for HR Employees writes and operator actions."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.domains.employees.engine import engine
from app.domains.employees.policies import employees_gate_transition, employees_policy_card, employees_run_field_checks
from app.domains.employees.queries import employees_diff, employees_export_map
from app.domains.employees.reports import build_employees_reporter


class EmployeesService:
    """Coordinates validation, policy, persistence, and briefings for HR Employees."""

    def list_view(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        rows = engine.list_records(filters)
        reporter = build_employees_reporter(rows)
        return {
            'rows': rows,
            'kpis': engine.kpi_pack(),
            'pack': reporter.pack(),
        }

    def detail_view(self, record_id: str) -> dict[str, Any] | None:
        row = engine.get(record_id)
        if row is None:
            return None
        card = employees_policy_card(row)
        return {'record': row, 'policy': card}

    def create_from_form(self, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        field_errors = employees_run_field_checks(payload)
        if field_errors:
            return None, field_errors
        return engine.create(payload)

    def update_from_form(self, record_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        merged = deepcopy(current)
        merged.update(payload)
        field_errors = employees_run_field_checks(merged)
        if field_errors:
            return None, field_errors
        row, errors = engine.update(record_id, payload)
        if row:
            row['_diff'] = employees_diff(current, row)
        return row, errors

    def move_status(self, record_id: str, new_status: str) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        errors = employees_gate_transition(str(current.get('status') or ''), new_status)
        if errors:
            return None, errors
        return engine.transition(record_id, new_status)

    def export_maps(self) -> list[dict[str, str]]:
        return [employees_export_map(row) for row in engine.list_records()]

    def seed_if_empty(self, count: int = 10) -> int:
        return engine.seed_demo(count)


service = EmployeesService()


def employees_safe_payload(form: dict[str, Any]) -> dict[str, Any]:
    allowed = {name for name in ['employee_no', 'full_name', 'cost_center', 'hire_on', 'fte_bps', 'status']}
    clean = {}
    for name, value in form.items():
        if name in allowed or name in {'id', 'status'}:
            clean[name] = value
    return clean


def employees_can_delete(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status == 'active':
        return True
    return int(row.get('health_score') or 0) < 20


def employees_next_statuses(current: str) -> list[str]:
    if current not in ['active', 'leave', 'terminated']:
        return list(['active', 'leave', 'terminated'])
    index = ['active', 'leave', 'terminated'].index(current)
    options = [current]
    if index + 1 < len(['active', 'leave', 'terminated']):
        options.append(['active', 'leave', 'terminated'][index + 1])
    if index > 0:
        options.append(['active', 'leave', 'terminated'][index - 1])
    unique = []
    for item in options:
        if item not in unique:
            unique.append(item)
    return unique


def employees_operator_actions(row: dict[str, Any]) -> list[dict[str, str]]:
    actions = [{'code': 'edit', 'label': 'Edit record'}]
    for status in employees_next_statuses(str(row.get('status') or '')):
        actions.append({'code': 'status:' + status, 'label': 'Move to ' + status})
    if employees_can_delete(row):
        actions.append({'code': 'delete', 'label': 'Remove record'})
    return actions


def employees_toast(action: str, ok: bool) -> str:
    if ok:
        return f'HR Employees {action} completed.'
    return f'HR Employees {action} was blocked by policy.'


def employees_dashboard_chip(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'key': 'employees',
        'title': 'HR Employees',
        'count': len(rows),
        'hot': len([row for row in rows if int(row.get('health_score') or 0) < 45]),
    }

def employees_form_help_employee_no() -> str:
    return 'Enter Employee No for HR Employees. Local validation runs on save.'


def employees_form_help_full_name() -> str:
    return 'Enter Full Name for HR Employees. Local validation runs on save.'


def employees_form_help_cost_center() -> str:
    return 'Enter Cost Center for HR Employees. Local validation runs on save.'


def employees_form_help_hire_on() -> str:
    return 'Enter Hire On for HR Employees. Local validation runs on save.'


def employees_form_help_fte_bps() -> str:
    return 'Enter Fte Bps for HR Employees. Local validation runs on save.'


def employees_form_help_status() -> str:
    return 'Enter Status for HR Employees. Local validation runs on save.'


FORM_HELP_EMPLOYEES = {
    'employee_no': employees_form_help_employee_no(),
    'full_name': employees_form_help_full_name(),
    'cost_center': employees_form_help_cost_center(),
    'hire_on': employees_form_help_hire_on(),
    'fte_bps': employees_form_help_fte_bps(),
    'status': employees_form_help_status(),
}


def employees_form_help() -> dict[str, str]:
    return dict(FORM_HELP_EMPLOYEES)

