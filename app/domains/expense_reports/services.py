"""Application service for Expense Reports writes and operator actions."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.domains.expense_reports.engine import engine
from app.domains.expense_reports.policies import expense_reports_gate_transition, expense_reports_policy_card, expense_reports_run_field_checks
from app.domains.expense_reports.queries import expense_reports_diff, expense_reports_export_map
from app.domains.expense_reports.reports import build_expense_reports_reporter


class ExpenseReportsService:
    """Coordinates validation, policy, persistence, and briefings for Expense Reports."""

    def list_view(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        rows = engine.list_records(filters)
        reporter = build_expense_reports_reporter(rows)
        return {
            'rows': rows,
            'kpis': engine.kpi_pack(),
            'pack': reporter.pack(),
        }

    def detail_view(self, record_id: str) -> dict[str, Any] | None:
        row = engine.get(record_id)
        if row is None:
            return None
        card = expense_reports_policy_card(row)
        return {'record': row, 'policy': card}

    def create_from_form(self, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        field_errors = expense_reports_run_field_checks(payload)
        if field_errors:
            return None, field_errors
        return engine.create(payload)

    def update_from_form(self, record_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        merged = deepcopy(current)
        merged.update(payload)
        field_errors = expense_reports_run_field_checks(merged)
        if field_errors:
            return None, field_errors
        row, errors = engine.update(record_id, payload)
        if row:
            row['_diff'] = expense_reports_diff(current, row)
        return row, errors

    def move_status(self, record_id: str, new_status: str) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        errors = expense_reports_gate_transition(str(current.get('status') or ''), new_status)
        if errors:
            return None, errors
        return engine.transition(record_id, new_status)

    def export_maps(self) -> list[dict[str, str]]:
        return [expense_reports_export_map(row) for row in engine.list_records()]

    def seed_if_empty(self, count: int = 10) -> int:
        return engine.seed_demo(count)


service = ExpenseReportsService()


def expense_reports_safe_payload(form: dict[str, Any]) -> dict[str, Any]:
    allowed = {name for name in ['report_no', 'employee_no', 'amount_cents', 'cost_center', 'submitted_on', 'status']}
    clean = {}
    for name, value in form.items():
        if name in allowed or name in {'id', 'status'}:
            clean[name] = value
    return clean


def expense_reports_can_delete(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status == 'draft':
        return True
    return int(row.get('health_score') or 0) < 20


def expense_reports_next_statuses(current: str) -> list[str]:
    if current not in ['draft', 'submitted', 'approved', 'paid', 'rejected']:
        return list(['draft', 'submitted', 'approved', 'paid', 'rejected'])
    index = ['draft', 'submitted', 'approved', 'paid', 'rejected'].index(current)
    options = [current]
    if index + 1 < len(['draft', 'submitted', 'approved', 'paid', 'rejected']):
        options.append(['draft', 'submitted', 'approved', 'paid', 'rejected'][index + 1])
    if index > 0:
        options.append(['draft', 'submitted', 'approved', 'paid', 'rejected'][index - 1])
    unique = []
    for item in options:
        if item not in unique:
            unique.append(item)
    return unique


def expense_reports_operator_actions(row: dict[str, Any]) -> list[dict[str, str]]:
    actions = [{'code': 'edit', 'label': 'Edit record'}]
    for status in expense_reports_next_statuses(str(row.get('status') or '')):
        actions.append({'code': 'status:' + status, 'label': 'Move to ' + status})
    if expense_reports_can_delete(row):
        actions.append({'code': 'delete', 'label': 'Remove record'})
    return actions


def expense_reports_toast(action: str, ok: bool) -> str:
    if ok:
        return f'Expense Reports {action} completed.'
    return f'Expense Reports {action} was blocked by policy.'


def expense_reports_dashboard_chip(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'key': 'expense_reports',
        'title': 'Expense Reports',
        'count': len(rows),
        'hot': len([row for row in rows if int(row.get('health_score') or 0) < 45]),
    }

def expense_reports_form_help_report_no() -> str:
    return 'Enter Report No for Expense Reports. Local validation runs on save.'


def expense_reports_form_help_employee_no() -> str:
    return 'Enter Employee No for Expense Reports. Local validation runs on save.'


def expense_reports_form_help_amount_cents() -> str:
    return 'Enter Amount Cents for Expense Reports. Local validation runs on save.'


def expense_reports_form_help_cost_center() -> str:
    return 'Enter Cost Center for Expense Reports. Local validation runs on save.'


def expense_reports_form_help_submitted_on() -> str:
    return 'Enter Submitted On for Expense Reports. Local validation runs on save.'


def expense_reports_form_help_status() -> str:
    return 'Enter Status for Expense Reports. Local validation runs on save.'


FORM_HELP_EXPENSE_REPORTS = {
    'report_no': expense_reports_form_help_report_no(),
    'employee_no': expense_reports_form_help_employee_no(),
    'amount_cents': expense_reports_form_help_amount_cents(),
    'cost_center': expense_reports_form_help_cost_center(),
    'submitted_on': expense_reports_form_help_submitted_on(),
    'status': expense_reports_form_help_status(),
}


def expense_reports_form_help() -> dict[str, str]:
    return dict(FORM_HELP_EXPENSE_REPORTS)

