"""Application service for Leave Requests writes and operator actions."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.domains.leave_requests.engine import engine
from app.domains.leave_requests.policies import leave_requests_gate_transition, leave_requests_policy_card, leave_requests_run_field_checks
from app.domains.leave_requests.queries import leave_requests_diff, leave_requests_export_map
from app.domains.leave_requests.reports import build_leave_requests_reporter


class LeaveRequestsService:
    """Coordinates validation, policy, persistence, and briefings for Leave Requests."""

    def list_view(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        rows = engine.list_records(filters)
        reporter = build_leave_requests_reporter(rows)
        return {
            'rows': rows,
            'kpis': engine.kpi_pack(),
            'pack': reporter.pack(),
        }

    def detail_view(self, record_id: str) -> dict[str, Any] | None:
        row = engine.get(record_id)
        if row is None:
            return None
        card = leave_requests_policy_card(row)
        return {'record': row, 'policy': card}

    def create_from_form(self, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        field_errors = leave_requests_run_field_checks(payload)
        if field_errors:
            return None, field_errors
        return engine.create(payload)

    def update_from_form(self, record_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        merged = deepcopy(current)
        merged.update(payload)
        field_errors = leave_requests_run_field_checks(merged)
        if field_errors:
            return None, field_errors
        row, errors = engine.update(record_id, payload)
        if row:
            row['_diff'] = leave_requests_diff(current, row)
        return row, errors

    def move_status(self, record_id: str, new_status: str) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        errors = leave_requests_gate_transition(str(current.get('status') or ''), new_status)
        if errors:
            return None, errors
        return engine.transition(record_id, new_status)

    def export_maps(self) -> list[dict[str, str]]:
        return [leave_requests_export_map(row) for row in engine.list_records()]

    def seed_if_empty(self, count: int = 10) -> int:
        return engine.seed_demo(count)


service = LeaveRequestsService()


def leave_requests_safe_payload(form: dict[str, Any]) -> dict[str, Any]:
    allowed = {name for name in ['employee_no', 'leave_type', 'starts_on', 'ends_on', 'days', 'status']}
    clean = {}
    for name, value in form.items():
        if name in allowed or name in {'id', 'status'}:
            clean[name] = value
    return clean


def leave_requests_can_delete(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status == 'submitted':
        return True
    return int(row.get('health_score') or 0) < 20


def leave_requests_next_statuses(current: str) -> list[str]:
    if current not in ['submitted', 'approved', 'rejected', 'taken']:
        return list(['submitted', 'approved', 'rejected', 'taken'])
    index = ['submitted', 'approved', 'rejected', 'taken'].index(current)
    options = [current]
    if index + 1 < len(['submitted', 'approved', 'rejected', 'taken']):
        options.append(['submitted', 'approved', 'rejected', 'taken'][index + 1])
    if index > 0:
        options.append(['submitted', 'approved', 'rejected', 'taken'][index - 1])
    unique = []
    for item in options:
        if item not in unique:
            unique.append(item)
    return unique


def leave_requests_operator_actions(row: dict[str, Any]) -> list[dict[str, str]]:
    actions = [{'code': 'edit', 'label': 'Edit record'}]
    for status in leave_requests_next_statuses(str(row.get('status') or '')):
        actions.append({'code': 'status:' + status, 'label': 'Move to ' + status})
    if leave_requests_can_delete(row):
        actions.append({'code': 'delete', 'label': 'Remove record'})
    return actions


def leave_requests_toast(action: str, ok: bool) -> str:
    if ok:
        return f'Leave Requests {action} completed.'
    return f'Leave Requests {action} was blocked by policy.'


def leave_requests_dashboard_chip(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'key': 'leave_requests',
        'title': 'Leave Requests',
        'count': len(rows),
        'hot': len([row for row in rows if int(row.get('health_score') or 0) < 45]),
    }

def leave_requests_form_help_employee_no() -> str:
    return 'Enter Employee No for Leave Requests. Local validation runs on save.'


def leave_requests_form_help_leave_type() -> str:
    return 'Enter Leave Type for Leave Requests. Local validation runs on save.'


def leave_requests_form_help_starts_on() -> str:
    return 'Enter Starts On for Leave Requests. Local validation runs on save.'


def leave_requests_form_help_ends_on() -> str:
    return 'Enter Ends On for Leave Requests. Local validation runs on save.'


def leave_requests_form_help_days() -> str:
    return 'Enter Days for Leave Requests. Local validation runs on save.'


def leave_requests_form_help_status() -> str:
    return 'Enter Status for Leave Requests. Local validation runs on save.'


FORM_HELP_LEAVE_REQUESTS = {
    'employee_no': leave_requests_form_help_employee_no(),
    'leave_type': leave_requests_form_help_leave_type(),
    'starts_on': leave_requests_form_help_starts_on(),
    'ends_on': leave_requests_form_help_ends_on(),
    'days': leave_requests_form_help_days(),
    'status': leave_requests_form_help_status(),
}


def leave_requests_form_help() -> dict[str, str]:
    return dict(FORM_HELP_LEAVE_REQUESTS)

