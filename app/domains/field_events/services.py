"""Application service for Field Events writes and operator actions."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.domains.field_events.engine import engine
from app.domains.field_events.policies import field_events_gate_transition, field_events_policy_card, field_events_run_field_checks
from app.domains.field_events.queries import field_events_diff, field_events_export_map
from app.domains.field_events.reports import build_field_events_reporter


class FieldEventsService:
    """Coordinates validation, policy, persistence, and briefings for Field Events."""

    def list_view(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        rows = engine.list_records(filters)
        reporter = build_field_events_reporter(rows)
        return {
            'rows': rows,
            'kpis': engine.kpi_pack(),
            'pack': reporter.pack(),
        }

    def detail_view(self, record_id: str) -> dict[str, Any] | None:
        row = engine.get(record_id)
        if row is None:
            return None
        card = field_events_policy_card(row)
        return {'record': row, 'policy': card}

    def create_from_form(self, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        field_errors = field_events_run_field_checks(payload)
        if field_errors:
            return None, field_errors
        return engine.create(payload)

    def update_from_form(self, record_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        merged = deepcopy(current)
        merged.update(payload)
        field_errors = field_events_run_field_checks(merged)
        if field_errors:
            return None, field_errors
        row, errors = engine.update(record_id, payload)
        if row:
            row['_diff'] = field_events_diff(current, row)
        return row, errors

    def move_status(self, record_id: str, new_status: str) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        errors = field_events_gate_transition(str(current.get('status') or ''), new_status)
        if errors:
            return None, errors
        return engine.transition(record_id, new_status)

    def export_maps(self) -> list[dict[str, str]]:
        return [field_events_export_map(row) for row in engine.list_records()]

    def seed_if_empty(self, count: int = 10) -> int:
        return engine.seed_demo(count)


service = FieldEventsService()


def field_events_safe_payload(form: dict[str, Any]) -> dict[str, Any]:
    allowed = {name for name in ['event_code', 'city', 'starts_on', 'budget_cents', 'status']}
    clean = {}
    for name, value in form.items():
        if name in allowed or name in {'id', 'status'}:
            clean[name] = value
    return clean


def field_events_can_delete(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status == 'proposed':
        return True
    return int(row.get('health_score') or 0) < 20


def field_events_next_statuses(current: str) -> list[str]:
    if current not in ['proposed', 'booked', 'live', 'wrap']:
        return list(['proposed', 'booked', 'live', 'wrap'])
    index = ['proposed', 'booked', 'live', 'wrap'].index(current)
    options = [current]
    if index + 1 < len(['proposed', 'booked', 'live', 'wrap']):
        options.append(['proposed', 'booked', 'live', 'wrap'][index + 1])
    if index > 0:
        options.append(['proposed', 'booked', 'live', 'wrap'][index - 1])
    unique = []
    for item in options:
        if item not in unique:
            unique.append(item)
    return unique


def field_events_operator_actions(row: dict[str, Any]) -> list[dict[str, str]]:
    actions = [{'code': 'edit', 'label': 'Edit record'}]
    for status in field_events_next_statuses(str(row.get('status') or '')):
        actions.append({'code': 'status:' + status, 'label': 'Move to ' + status})
    if field_events_can_delete(row):
        actions.append({'code': 'delete', 'label': 'Remove record'})
    return actions


def field_events_toast(action: str, ok: bool) -> str:
    if ok:
        return f'Field Events {action} completed.'
    return f'Field Events {action} was blocked by policy.'


def field_events_dashboard_chip(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'key': 'field_events',
        'title': 'Field Events',
        'count': len(rows),
        'hot': len([row for row in rows if int(row.get('health_score') or 0) < 45]),
    }

def field_events_form_help_event_code() -> str:
    return 'Enter Event Code for Field Events. Local validation runs on save.'


def field_events_form_help_city() -> str:
    return 'Enter City for Field Events. Local validation runs on save.'


def field_events_form_help_starts_on() -> str:
    return 'Enter Starts On for Field Events. Local validation runs on save.'


def field_events_form_help_budget_cents() -> str:
    return 'Enter Budget Cents for Field Events. Local validation runs on save.'


def field_events_form_help_status() -> str:
    return 'Enter Status for Field Events. Local validation runs on save.'


FORM_HELP_FIELD_EVENTS = {
    'event_code': field_events_form_help_event_code(),
    'city': field_events_form_help_city(),
    'starts_on': field_events_form_help_starts_on(),
    'budget_cents': field_events_form_help_budget_cents(),
    'status': field_events_form_help_status(),
}


def field_events_form_help() -> dict[str, str]:
    return dict(FORM_HELP_FIELD_EVENTS)

