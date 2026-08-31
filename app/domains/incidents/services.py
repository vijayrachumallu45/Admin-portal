"""Application service for Incident Room writes and operator actions."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.domains.incidents.engine import engine
from app.domains.incidents.policies import incidents_gate_transition, incidents_policy_card, incidents_run_field_checks
from app.domains.incidents.queries import incidents_diff, incidents_export_map
from app.domains.incidents.reports import build_incidents_reporter


class IncidentsService:
    """Coordinates validation, policy, persistence, and briefings for Incident Room."""

    def list_view(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        rows = engine.list_records(filters)
        reporter = build_incidents_reporter(rows)
        return {
            'rows': rows,
            'kpis': engine.kpi_pack(),
            'pack': reporter.pack(),
        }

    def detail_view(self, record_id: str) -> dict[str, Any] | None:
        row = engine.get(record_id)
        if row is None:
            return None
        card = incidents_policy_card(row)
        return {'record': row, 'policy': card}

    def create_from_form(self, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        field_errors = incidents_run_field_checks(payload)
        if field_errors:
            return None, field_errors
        return engine.create(payload)

    def update_from_form(self, record_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        merged = deepcopy(current)
        merged.update(payload)
        field_errors = incidents_run_field_checks(merged)
        if field_errors:
            return None, field_errors
        row, errors = engine.update(record_id, payload)
        if row:
            row['_diff'] = incidents_diff(current, row)
        return row, errors

    def move_status(self, record_id: str, new_status: str) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        errors = incidents_gate_transition(str(current.get('status') or ''), new_status)
        if errors:
            return None, errors
        return engine.transition(record_id, new_status)

    def export_maps(self) -> list[dict[str, str]]:
        return [incidents_export_map(row) for row in engine.list_records()]

    def seed_if_empty(self, count: int = 10) -> int:
        return engine.seed_demo(count)


service = IncidentsService()


def incidents_safe_payload(form: dict[str, Any]) -> dict[str, Any]:
    allowed = {name for name in ['incident_no', 'title', 'severity', 'commander', 'started_at', 'status']}
    clean = {}
    for name, value in form.items():
        if name in allowed or name in {'id', 'status'}:
            clean[name] = value
    return clean


def incidents_can_delete(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status == 'investigating':
        return True
    return int(row.get('health_score') or 0) < 20


def incidents_next_statuses(current: str) -> list[str]:
    if current not in ['investigating', 'identified', 'monitoring', 'resolved']:
        return list(['investigating', 'identified', 'monitoring', 'resolved'])
    index = ['investigating', 'identified', 'monitoring', 'resolved'].index(current)
    options = [current]
    if index + 1 < len(['investigating', 'identified', 'monitoring', 'resolved']):
        options.append(['investigating', 'identified', 'monitoring', 'resolved'][index + 1])
    if index > 0:
        options.append(['investigating', 'identified', 'monitoring', 'resolved'][index - 1])
    unique = []
    for item in options:
        if item not in unique:
            unique.append(item)
    return unique


def incidents_operator_actions(row: dict[str, Any]) -> list[dict[str, str]]:
    actions = [{'code': 'edit', 'label': 'Edit record'}]
    for status in incidents_next_statuses(str(row.get('status') or '')):
        actions.append({'code': 'status:' + status, 'label': 'Move to ' + status})
    if incidents_can_delete(row):
        actions.append({'code': 'delete', 'label': 'Remove record'})
    return actions


def incidents_toast(action: str, ok: bool) -> str:
    if ok:
        return f'Incident Room {action} completed.'
    return f'Incident Room {action} was blocked by policy.'


def incidents_dashboard_chip(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'key': 'incidents',
        'title': 'Incident Room',
        'count': len(rows),
        'hot': len([row for row in rows if int(row.get('health_score') or 0) < 45]),
    }

def incidents_form_help_incident_no() -> str:
    return 'Enter Incident No for Incident Room. Local validation runs on save.'


def incidents_form_help_title() -> str:
    return 'Enter Title for Incident Room. Local validation runs on save.'


def incidents_form_help_severity() -> str:
    return 'Enter Severity for Incident Room. Local validation runs on save.'


def incidents_form_help_commander() -> str:
    return 'Enter Commander for Incident Room. Local validation runs on save.'


def incidents_form_help_started_at() -> str:
    return 'Enter Started At for Incident Room. Local validation runs on save.'


def incidents_form_help_status() -> str:
    return 'Enter Status for Incident Room. Local validation runs on save.'


FORM_HELP_INCIDENTS = {
    'incident_no': incidents_form_help_incident_no(),
    'title': incidents_form_help_title(),
    'severity': incidents_form_help_severity(),
    'commander': incidents_form_help_commander(),
    'started_at': incidents_form_help_started_at(),
    'status': incidents_form_help_status(),
}


def incidents_form_help() -> dict[str, str]:
    return dict(FORM_HELP_INCIDENTS)

