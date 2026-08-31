"""Application service for Delivery Projects writes and operator actions."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.domains.projects.engine import engine
from app.domains.projects.policies import projects_gate_transition, projects_policy_card, projects_run_field_checks
from app.domains.projects.queries import projects_diff, projects_export_map
from app.domains.projects.reports import build_projects_reporter


class ProjectsService:
    """Coordinates validation, policy, persistence, and briefings for Delivery Projects."""

    def list_view(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        rows = engine.list_records(filters)
        reporter = build_projects_reporter(rows)
        return {
            'rows': rows,
            'kpis': engine.kpi_pack(),
            'pack': reporter.pack(),
        }

    def detail_view(self, record_id: str) -> dict[str, Any] | None:
        row = engine.get(record_id)
        if row is None:
            return None
        card = projects_policy_card(row)
        return {'record': row, 'policy': card}

    def create_from_form(self, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        field_errors = projects_run_field_checks(payload)
        if field_errors:
            return None, field_errors
        return engine.create(payload)

    def update_from_form(self, record_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        merged = deepcopy(current)
        merged.update(payload)
        field_errors = projects_run_field_checks(merged)
        if field_errors:
            return None, field_errors
        row, errors = engine.update(record_id, payload)
        if row:
            row['_diff'] = projects_diff(current, row)
        return row, errors

    def move_status(self, record_id: str, new_status: str) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        errors = projects_gate_transition(str(current.get('status') or ''), new_status)
        if errors:
            return None, errors
        return engine.transition(record_id, new_status)

    def export_maps(self) -> list[dict[str, str]]:
        return [projects_export_map(row) for row in engine.list_records()]

    def seed_if_empty(self, count: int = 10) -> int:
        return engine.seed_demo(count)


service = ProjectsService()


def projects_safe_payload(form: dict[str, Any]) -> dict[str, Any]:
    allowed = {name for name in ['project_code', 'name', 'sponsor', 'budget_cents', 'health', 'status']}
    clean = {}
    for name, value in form.items():
        if name in allowed or name in {'id', 'status'}:
            clean[name] = value
    return clean


def projects_can_delete(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status == 'planning':
        return True
    return int(row.get('health_score') or 0) < 20


def projects_next_statuses(current: str) -> list[str]:
    if current not in ['planning', 'active', 'blocked', 'done']:
        return list(['planning', 'active', 'blocked', 'done'])
    index = ['planning', 'active', 'blocked', 'done'].index(current)
    options = [current]
    if index + 1 < len(['planning', 'active', 'blocked', 'done']):
        options.append(['planning', 'active', 'blocked', 'done'][index + 1])
    if index > 0:
        options.append(['planning', 'active', 'blocked', 'done'][index - 1])
    unique = []
    for item in options:
        if item not in unique:
            unique.append(item)
    return unique


def projects_operator_actions(row: dict[str, Any]) -> list[dict[str, str]]:
    actions = [{'code': 'edit', 'label': 'Edit record'}]
    for status in projects_next_statuses(str(row.get('status') or '')):
        actions.append({'code': 'status:' + status, 'label': 'Move to ' + status})
    if projects_can_delete(row):
        actions.append({'code': 'delete', 'label': 'Remove record'})
    return actions


def projects_toast(action: str, ok: bool) -> str:
    if ok:
        return f'Delivery Projects {action} completed.'
    return f'Delivery Projects {action} was blocked by policy.'


def projects_dashboard_chip(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'key': 'projects',
        'title': 'Delivery Projects',
        'count': len(rows),
        'hot': len([row for row in rows if int(row.get('health_score') or 0) < 45]),
    }

def projects_form_help_project_code() -> str:
    return 'Enter Project Code for Delivery Projects. Local validation runs on save.'


def projects_form_help_name() -> str:
    return 'Enter Name for Delivery Projects. Local validation runs on save.'


def projects_form_help_sponsor() -> str:
    return 'Enter Sponsor for Delivery Projects. Local validation runs on save.'


def projects_form_help_budget_cents() -> str:
    return 'Enter Budget Cents for Delivery Projects. Local validation runs on save.'


def projects_form_help_health() -> str:
    return 'Enter Health for Delivery Projects. Local validation runs on save.'


def projects_form_help_status() -> str:
    return 'Enter Status for Delivery Projects. Local validation runs on save.'


FORM_HELP_PROJECTS = {
    'project_code': projects_form_help_project_code(),
    'name': projects_form_help_name(),
    'sponsor': projects_form_help_sponsor(),
    'budget_cents': projects_form_help_budget_cents(),
    'health': projects_form_help_health(),
    'status': projects_form_help_status(),
}


def projects_form_help() -> dict[str, str]:
    return dict(FORM_HELP_PROJECTS)

