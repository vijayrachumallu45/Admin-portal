"""Application service for People Directory writes and operator actions."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.domains.directory_users.engine import engine
from app.domains.directory_users.policies import directory_users_gate_transition, directory_users_policy_card, directory_users_run_field_checks
from app.domains.directory_users.queries import directory_users_diff, directory_users_export_map
from app.domains.directory_users.reports import build_directory_users_reporter


class DirectoryUsersService:
    """Coordinates validation, policy, persistence, and briefings for People Directory."""

    def list_view(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        rows = engine.list_records(filters)
        reporter = build_directory_users_reporter(rows)
        return {
            'rows': rows,
            'kpis': engine.kpi_pack(),
            'pack': reporter.pack(),
        }

    def detail_view(self, record_id: str) -> dict[str, Any] | None:
        row = engine.get(record_id)
        if row is None:
            return None
        card = directory_users_policy_card(row)
        return {'record': row, 'policy': card}

    def create_from_form(self, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        field_errors = directory_users_run_field_checks(payload)
        if field_errors:
            return None, field_errors
        return engine.create(payload)

    def update_from_form(self, record_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        merged = deepcopy(current)
        merged.update(payload)
        field_errors = directory_users_run_field_checks(merged)
        if field_errors:
            return None, field_errors
        row, errors = engine.update(record_id, payload)
        if row:
            row['_diff'] = directory_users_diff(current, row)
        return row, errors

    def move_status(self, record_id: str, new_status: str) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        errors = directory_users_gate_transition(str(current.get('status') or ''), new_status)
        if errors:
            return None, errors
        return engine.transition(record_id, new_status)

    def export_maps(self) -> list[dict[str, str]]:
        return [directory_users_export_map(row) for row in engine.list_records()]

    def seed_if_empty(self, count: int = 10) -> int:
        return engine.seed_demo(count)


service = DirectoryUsersService()


def directory_users_safe_payload(form: dict[str, Any]) -> dict[str, Any]:
    allowed = {name for name in ['email', 'full_name', 'job_title', 'department', 'manager_email', 'location', 'band', 'status']}
    clean = {}
    for name, value in form.items():
        if name in allowed or name in {'id', 'status'}:
            clean[name] = value
    return clean


def directory_users_can_delete(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status == 'invited':
        return True
    return int(row.get('health_score') or 0) < 20


def directory_users_next_statuses(current: str) -> list[str]:
    if current not in ['invited', 'active', 'leave', 'offboarded']:
        return list(['invited', 'active', 'leave', 'offboarded'])
    index = ['invited', 'active', 'leave', 'offboarded'].index(current)
    options = [current]
    if index + 1 < len(['invited', 'active', 'leave', 'offboarded']):
        options.append(['invited', 'active', 'leave', 'offboarded'][index + 1])
    if index > 0:
        options.append(['invited', 'active', 'leave', 'offboarded'][index - 1])
    unique = []
    for item in options:
        if item not in unique:
            unique.append(item)
    return unique


def directory_users_operator_actions(row: dict[str, Any]) -> list[dict[str, str]]:
    actions = [{'code': 'edit', 'label': 'Edit record'}]
    for status in directory_users_next_statuses(str(row.get('status') or '')):
        actions.append({'code': 'status:' + status, 'label': 'Move to ' + status})
    if directory_users_can_delete(row):
        actions.append({'code': 'delete', 'label': 'Remove record'})
    return actions


def directory_users_toast(action: str, ok: bool) -> str:
    if ok:
        return f'People Directory {action} completed.'
    return f'People Directory {action} was blocked by policy.'


def directory_users_dashboard_chip(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'key': 'directory_users',
        'title': 'People Directory',
        'count': len(rows),
        'hot': len([row for row in rows if int(row.get('health_score') or 0) < 45]),
    }

def directory_users_form_help_email() -> str:
    return 'Enter Email for People Directory. Local validation runs on save.'


def directory_users_form_help_full_name() -> str:
    return 'Enter Full Name for People Directory. Local validation runs on save.'


def directory_users_form_help_job_title() -> str:
    return 'Enter Job Title for People Directory. Local validation runs on save.'


def directory_users_form_help_department() -> str:
    return 'Enter Department for People Directory. Local validation runs on save.'


def directory_users_form_help_manager_email() -> str:
    return 'Enter Manager Email for People Directory. Local validation runs on save.'


def directory_users_form_help_location() -> str:
    return 'Enter Location for People Directory. Local validation runs on save.'


def directory_users_form_help_band() -> str:
    return 'Enter Band for People Directory. Local validation runs on save.'


def directory_users_form_help_status() -> str:
    return 'Enter Status for People Directory. Local validation runs on save.'


FORM_HELP_DIRECTORY_USERS = {
    'email': directory_users_form_help_email(),
    'full_name': directory_users_form_help_full_name(),
    'job_title': directory_users_form_help_job_title(),
    'department': directory_users_form_help_department(),
    'manager_email': directory_users_form_help_manager_email(),
    'location': directory_users_form_help_location(),
    'band': directory_users_form_help_band(),
    'status': directory_users_form_help_status(),
}


def directory_users_form_help() -> dict[str, str]:
    return dict(FORM_HELP_DIRECTORY_USERS)

