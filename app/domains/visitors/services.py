"""Application service for Visitor Desk writes and operator actions."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.domains.visitors.engine import engine
from app.domains.visitors.policies import visitors_gate_transition, visitors_policy_card, visitors_run_field_checks
from app.domains.visitors.queries import visitors_diff, visitors_export_map
from app.domains.visitors.reports import build_visitors_reporter


class VisitorsService:
    """Coordinates validation, policy, persistence, and briefings for Visitor Desk."""

    def list_view(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        rows = engine.list_records(filters)
        reporter = build_visitors_reporter(rows)
        return {
            'rows': rows,
            'kpis': engine.kpi_pack(),
            'pack': reporter.pack(),
        }

    def detail_view(self, record_id: str) -> dict[str, Any] | None:
        row = engine.get(record_id)
        if row is None:
            return None
        card = visitors_policy_card(row)
        return {'record': row, 'policy': card}

    def create_from_form(self, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        field_errors = visitors_run_field_checks(payload)
        if field_errors:
            return None, field_errors
        return engine.create(payload)

    def update_from_form(self, record_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        merged = deepcopy(current)
        merged.update(payload)
        field_errors = visitors_run_field_checks(merged)
        if field_errors:
            return None, field_errors
        row, errors = engine.update(record_id, payload)
        if row:
            row['_diff'] = visitors_diff(current, row)
        return row, errors

    def move_status(self, record_id: str, new_status: str) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        errors = visitors_gate_transition(str(current.get('status') or ''), new_status)
        if errors:
            return None, errors
        return engine.transition(record_id, new_status)

    def export_maps(self) -> list[dict[str, str]]:
        return [visitors_export_map(row) for row in engine.list_records()]

    def seed_if_empty(self, count: int = 10) -> int:
        return engine.seed_demo(count)


service = VisitorsService()


def visitors_safe_payload(form: dict[str, Any]) -> dict[str, Any]:
    allowed = {name for name in ['visitor_name', 'host_name', 'company', 'arrives_on', 'status']}
    clean = {}
    for name, value in form.items():
        if name in allowed or name in {'id', 'status'}:
            clean[name] = value
    return clean


def visitors_can_delete(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status == 'expected':
        return True
    return int(row.get('health_score') or 0) < 20


def visitors_next_statuses(current: str) -> list[str]:
    if current not in ['expected', 'on_site', 'departed']:
        return list(['expected', 'on_site', 'departed'])
    index = ['expected', 'on_site', 'departed'].index(current)
    options = [current]
    if index + 1 < len(['expected', 'on_site', 'departed']):
        options.append(['expected', 'on_site', 'departed'][index + 1])
    if index > 0:
        options.append(['expected', 'on_site', 'departed'][index - 1])
    unique = []
    for item in options:
        if item not in unique:
            unique.append(item)
    return unique


def visitors_operator_actions(row: dict[str, Any]) -> list[dict[str, str]]:
    actions = [{'code': 'edit', 'label': 'Edit record'}]
    for status in visitors_next_statuses(str(row.get('status') or '')):
        actions.append({'code': 'status:' + status, 'label': 'Move to ' + status})
    if visitors_can_delete(row):
        actions.append({'code': 'delete', 'label': 'Remove record'})
    return actions


def visitors_toast(action: str, ok: bool) -> str:
    if ok:
        return f'Visitor Desk {action} completed.'
    return f'Visitor Desk {action} was blocked by policy.'


def visitors_dashboard_chip(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'key': 'visitors',
        'title': 'Visitor Desk',
        'count': len(rows),
        'hot': len([row for row in rows if int(row.get('health_score') or 0) < 45]),
    }

def visitors_form_help_visitor_name() -> str:
    return 'Enter Visitor Name for Visitor Desk. Local validation runs on save.'


def visitors_form_help_host_name() -> str:
    return 'Enter Host Name for Visitor Desk. Local validation runs on save.'


def visitors_form_help_company() -> str:
    return 'Enter Company for Visitor Desk. Local validation runs on save.'


def visitors_form_help_arrives_on() -> str:
    return 'Enter Arrives On for Visitor Desk. Local validation runs on save.'


def visitors_form_help_status() -> str:
    return 'Enter Status for Visitor Desk. Local validation runs on save.'


FORM_HELP_VISITORS = {
    'visitor_name': visitors_form_help_visitor_name(),
    'host_name': visitors_form_help_host_name(),
    'company': visitors_form_help_company(),
    'arrives_on': visitors_form_help_arrives_on(),
    'status': visitors_form_help_status(),
}


def visitors_form_help() -> dict[str, str]:
    return dict(FORM_HELP_VISITORS)

