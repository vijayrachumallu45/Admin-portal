"""Application service for Postmortems writes and operator actions."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.domains.postmortems.engine import engine
from app.domains.postmortems.policies import postmortems_gate_transition, postmortems_policy_card, postmortems_run_field_checks
from app.domains.postmortems.queries import postmortems_diff, postmortems_export_map
from app.domains.postmortems.reports import build_postmortems_reporter


class PostmortemsService:
    """Coordinates validation, policy, persistence, and briefings for Postmortems."""

    def list_view(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        rows = engine.list_records(filters)
        reporter = build_postmortems_reporter(rows)
        return {
            'rows': rows,
            'kpis': engine.kpi_pack(),
            'pack': reporter.pack(),
        }

    def detail_view(self, record_id: str) -> dict[str, Any] | None:
        row = engine.get(record_id)
        if row is None:
            return None
        card = postmortems_policy_card(row)
        return {'record': row, 'policy': card}

    def create_from_form(self, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        field_errors = postmortems_run_field_checks(payload)
        if field_errors:
            return None, field_errors
        return engine.create(payload)

    def update_from_form(self, record_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        merged = deepcopy(current)
        merged.update(payload)
        field_errors = postmortems_run_field_checks(merged)
        if field_errors:
            return None, field_errors
        row, errors = engine.update(record_id, payload)
        if row:
            row['_diff'] = postmortems_diff(current, row)
        return row, errors

    def move_status(self, record_id: str, new_status: str) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        errors = postmortems_gate_transition(str(current.get('status') or ''), new_status)
        if errors:
            return None, errors
        return engine.transition(record_id, new_status)

    def export_maps(self) -> list[dict[str, str]]:
        return [postmortems_export_map(row) for row in engine.list_records()]

    def seed_if_empty(self, count: int = 10) -> int:
        return engine.seed_demo(count)


service = PostmortemsService()


def postmortems_safe_payload(form: dict[str, Any]) -> dict[str, Any]:
    allowed = {name for name in ['doc_no', 'incident_no', 'severity', 'due_on', 'status']}
    clean = {}
    for name, value in form.items():
        if name in allowed or name in {'id', 'status'}:
            clean[name] = value
    return clean


def postmortems_can_delete(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status == 'writing':
        return True
    return int(row.get('health_score') or 0) < 20


def postmortems_next_statuses(current: str) -> list[str]:
    if current not in ['writing', 'review', 'published']:
        return list(['writing', 'review', 'published'])
    index = ['writing', 'review', 'published'].index(current)
    options = [current]
    if index + 1 < len(['writing', 'review', 'published']):
        options.append(['writing', 'review', 'published'][index + 1])
    if index > 0:
        options.append(['writing', 'review', 'published'][index - 1])
    unique = []
    for item in options:
        if item not in unique:
            unique.append(item)
    return unique


def postmortems_operator_actions(row: dict[str, Any]) -> list[dict[str, str]]:
    actions = [{'code': 'edit', 'label': 'Edit record'}]
    for status in postmortems_next_statuses(str(row.get('status') or '')):
        actions.append({'code': 'status:' + status, 'label': 'Move to ' + status})
    if postmortems_can_delete(row):
        actions.append({'code': 'delete', 'label': 'Remove record'})
    return actions


def postmortems_toast(action: str, ok: bool) -> str:
    if ok:
        return f'Postmortems {action} completed.'
    return f'Postmortems {action} was blocked by policy.'


def postmortems_dashboard_chip(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'key': 'postmortems',
        'title': 'Postmortems',
        'count': len(rows),
        'hot': len([row for row in rows if int(row.get('health_score') or 0) < 45]),
    }

def postmortems_form_help_doc_no() -> str:
    return 'Enter Doc No for Postmortems. Local validation runs on save.'


def postmortems_form_help_incident_no() -> str:
    return 'Enter Incident No for Postmortems. Local validation runs on save.'


def postmortems_form_help_severity() -> str:
    return 'Enter Severity for Postmortems. Local validation runs on save.'


def postmortems_form_help_due_on() -> str:
    return 'Enter Due On for Postmortems. Local validation runs on save.'


def postmortems_form_help_status() -> str:
    return 'Enter Status for Postmortems. Local validation runs on save.'


FORM_HELP_POSTMORTEMS = {
    'doc_no': postmortems_form_help_doc_no(),
    'incident_no': postmortems_form_help_incident_no(),
    'severity': postmortems_form_help_severity(),
    'due_on': postmortems_form_help_due_on(),
    'status': postmortems_form_help_status(),
}


def postmortems_form_help() -> dict[str, str]:
    return dict(FORM_HELP_POSTMORTEMS)

