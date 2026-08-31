"""Application service for Change Requests writes and operator actions."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.domains.change_requests.engine import engine
from app.domains.change_requests.policies import change_requests_gate_transition, change_requests_policy_card, change_requests_run_field_checks
from app.domains.change_requests.queries import change_requests_diff, change_requests_export_map
from app.domains.change_requests.reports import build_change_requests_reporter


class ChangeRequestsService:
    """Coordinates validation, policy, persistence, and briefings for Change Requests."""

    def list_view(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        rows = engine.list_records(filters)
        reporter = build_change_requests_reporter(rows)
        return {
            'rows': rows,
            'kpis': engine.kpi_pack(),
            'pack': reporter.pack(),
        }

    def detail_view(self, record_id: str) -> dict[str, Any] | None:
        row = engine.get(record_id)
        if row is None:
            return None
        card = change_requests_policy_card(row)
        return {'record': row, 'policy': card}

    def create_from_form(self, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        field_errors = change_requests_run_field_checks(payload)
        if field_errors:
            return None, field_errors
        return engine.create(payload)

    def update_from_form(self, record_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        merged = deepcopy(current)
        merged.update(payload)
        field_errors = change_requests_run_field_checks(merged)
        if field_errors:
            return None, field_errors
        row, errors = engine.update(record_id, payload)
        if row:
            row['_diff'] = change_requests_diff(current, row)
        return row, errors

    def move_status(self, record_id: str, new_status: str) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        errors = change_requests_gate_transition(str(current.get('status') or ''), new_status)
        if errors:
            return None, errors
        return engine.transition(record_id, new_status)

    def export_maps(self) -> list[dict[str, str]]:
        return [change_requests_export_map(row) for row in engine.list_records()]

    def seed_if_empty(self, count: int = 10) -> int:
        return engine.seed_demo(count)


service = ChangeRequestsService()


def change_requests_safe_payload(form: dict[str, Any]) -> dict[str, Any]:
    allowed = {name for name in ['change_no', 'summary', 'risk', 'window_start', 'owner', 'status']}
    clean = {}
    for name, value in form.items():
        if name in allowed or name in {'id', 'status'}:
            clean[name] = value
    return clean


def change_requests_can_delete(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status == 'draft':
        return True
    return int(row.get('health_score') or 0) < 20


def change_requests_next_statuses(current: str) -> list[str]:
    if current not in ['draft', 'cab', 'approved', 'executed', 'failed']:
        return list(['draft', 'cab', 'approved', 'executed', 'failed'])
    index = ['draft', 'cab', 'approved', 'executed', 'failed'].index(current)
    options = [current]
    if index + 1 < len(['draft', 'cab', 'approved', 'executed', 'failed']):
        options.append(['draft', 'cab', 'approved', 'executed', 'failed'][index + 1])
    if index > 0:
        options.append(['draft', 'cab', 'approved', 'executed', 'failed'][index - 1])
    unique = []
    for item in options:
        if item not in unique:
            unique.append(item)
    return unique


def change_requests_operator_actions(row: dict[str, Any]) -> list[dict[str, str]]:
    actions = [{'code': 'edit', 'label': 'Edit record'}]
    for status in change_requests_next_statuses(str(row.get('status') or '')):
        actions.append({'code': 'status:' + status, 'label': 'Move to ' + status})
    if change_requests_can_delete(row):
        actions.append({'code': 'delete', 'label': 'Remove record'})
    return actions


def change_requests_toast(action: str, ok: bool) -> str:
    if ok:
        return f'Change Requests {action} completed.'
    return f'Change Requests {action} was blocked by policy.'


def change_requests_dashboard_chip(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'key': 'change_requests',
        'title': 'Change Requests',
        'count': len(rows),
        'hot': len([row for row in rows if int(row.get('health_score') or 0) < 45]),
    }

def change_requests_form_help_change_no() -> str:
    return 'Enter Change No for Change Requests. Local validation runs on save.'


def change_requests_form_help_summary() -> str:
    return 'Enter Summary for Change Requests. Local validation runs on save.'


def change_requests_form_help_risk() -> str:
    return 'Enter Risk for Change Requests. Local validation runs on save.'


def change_requests_form_help_window_start() -> str:
    return 'Enter Window Start for Change Requests. Local validation runs on save.'


def change_requests_form_help_owner() -> str:
    return 'Enter Owner for Change Requests. Local validation runs on save.'


def change_requests_form_help_status() -> str:
    return 'Enter Status for Change Requests. Local validation runs on save.'


FORM_HELP_CHANGE_REQUESTS = {
    'change_no': change_requests_form_help_change_no(),
    'summary': change_requests_form_help_summary(),
    'risk': change_requests_form_help_risk(),
    'window_start': change_requests_form_help_window_start(),
    'owner': change_requests_form_help_owner(),
    'status': change_requests_form_help_status(),
}


def change_requests_form_help() -> dict[str, str]:
    return dict(FORM_HELP_CHANGE_REQUESTS)

