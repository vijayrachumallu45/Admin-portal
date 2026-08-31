"""Application service for Webinar Desk writes and operator actions."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.domains.webinars.engine import engine
from app.domains.webinars.policies import webinars_gate_transition, webinars_policy_card, webinars_run_field_checks
from app.domains.webinars.queries import webinars_diff, webinars_export_map
from app.domains.webinars.reports import build_webinars_reporter


class WebinarsService:
    """Coordinates validation, policy, persistence, and briefings for Webinar Desk."""

    def list_view(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        rows = engine.list_records(filters)
        reporter = build_webinars_reporter(rows)
        return {
            'rows': rows,
            'kpis': engine.kpi_pack(),
            'pack': reporter.pack(),
        }

    def detail_view(self, record_id: str) -> dict[str, Any] | None:
        row = engine.get(record_id)
        if row is None:
            return None
        card = webinars_policy_card(row)
        return {'record': row, 'policy': card}

    def create_from_form(self, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        field_errors = webinars_run_field_checks(payload)
        if field_errors:
            return None, field_errors
        return engine.create(payload)

    def update_from_form(self, record_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        merged = deepcopy(current)
        merged.update(payload)
        field_errors = webinars_run_field_checks(merged)
        if field_errors:
            return None, field_errors
        row, errors = engine.update(record_id, payload)
        if row:
            row['_diff'] = webinars_diff(current, row)
        return row, errors

    def move_status(self, record_id: str, new_status: str) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        errors = webinars_gate_transition(str(current.get('status') or ''), new_status)
        if errors:
            return None, errors
        return engine.transition(record_id, new_status)

    def export_maps(self) -> list[dict[str, str]]:
        return [webinars_export_map(row) for row in engine.list_records()]

    def seed_if_empty(self, count: int = 10) -> int:
        return engine.seed_demo(count)


service = WebinarsService()


def webinars_safe_payload(form: dict[str, Any]) -> dict[str, Any]:
    allowed = {name for name in ['webinar_code', 'title', 'host_name', 'starts_on', 'cap', 'status']}
    clean = {}
    for name, value in form.items():
        if name in allowed or name in {'id', 'status'}:
            clean[name] = value
    return clean


def webinars_can_delete(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status == 'planned':
        return True
    return int(row.get('health_score') or 0) < 20


def webinars_next_statuses(current: str) -> list[str]:
    if current not in ['planned', 'live', 'complete', 'cancelled']:
        return list(['planned', 'live', 'complete', 'cancelled'])
    index = ['planned', 'live', 'complete', 'cancelled'].index(current)
    options = [current]
    if index + 1 < len(['planned', 'live', 'complete', 'cancelled']):
        options.append(['planned', 'live', 'complete', 'cancelled'][index + 1])
    if index > 0:
        options.append(['planned', 'live', 'complete', 'cancelled'][index - 1])
    unique = []
    for item in options:
        if item not in unique:
            unique.append(item)
    return unique


def webinars_operator_actions(row: dict[str, Any]) -> list[dict[str, str]]:
    actions = [{'code': 'edit', 'label': 'Edit record'}]
    for status in webinars_next_statuses(str(row.get('status') or '')):
        actions.append({'code': 'status:' + status, 'label': 'Move to ' + status})
    if webinars_can_delete(row):
        actions.append({'code': 'delete', 'label': 'Remove record'})
    return actions


def webinars_toast(action: str, ok: bool) -> str:
    if ok:
        return f'Webinar Desk {action} completed.'
    return f'Webinar Desk {action} was blocked by policy.'


def webinars_dashboard_chip(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'key': 'webinars',
        'title': 'Webinar Desk',
        'count': len(rows),
        'hot': len([row for row in rows if int(row.get('health_score') or 0) < 45]),
    }

def webinars_form_help_webinar_code() -> str:
    return 'Enter Webinar Code for Webinar Desk. Local validation runs on save.'


def webinars_form_help_title() -> str:
    return 'Enter Title for Webinar Desk. Local validation runs on save.'


def webinars_form_help_host_name() -> str:
    return 'Enter Host Name for Webinar Desk. Local validation runs on save.'


def webinars_form_help_starts_on() -> str:
    return 'Enter Starts On for Webinar Desk. Local validation runs on save.'


def webinars_form_help_cap() -> str:
    return 'Enter Cap for Webinar Desk. Local validation runs on save.'


def webinars_form_help_status() -> str:
    return 'Enter Status for Webinar Desk. Local validation runs on save.'


FORM_HELP_WEBINARS = {
    'webinar_code': webinars_form_help_webinar_code(),
    'title': webinars_form_help_title(),
    'host_name': webinars_form_help_host_name(),
    'starts_on': webinars_form_help_starts_on(),
    'cap': webinars_form_help_cap(),
    'status': webinars_form_help_status(),
}


def webinars_form_help() -> dict[str, str]:
    return dict(FORM_HELP_WEBINARS)

