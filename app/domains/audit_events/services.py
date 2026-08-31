"""Application service for Audit Ledger writes and operator actions."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.domains.audit_events.engine import engine
from app.domains.audit_events.policies import audit_events_gate_transition, audit_events_policy_card, audit_events_run_field_checks
from app.domains.audit_events.queries import audit_events_diff, audit_events_export_map
from app.domains.audit_events.reports import build_audit_events_reporter


class AuditEventsService:
    """Coordinates validation, policy, persistence, and briefings for Audit Ledger."""

    def list_view(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        rows = engine.list_records(filters)
        reporter = build_audit_events_reporter(rows)
        return {
            'rows': rows,
            'kpis': engine.kpi_pack(),
            'pack': reporter.pack(),
        }

    def detail_view(self, record_id: str) -> dict[str, Any] | None:
        row = engine.get(record_id)
        if row is None:
            return None
        card = audit_events_policy_card(row)
        return {'record': row, 'policy': card}

    def create_from_form(self, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        field_errors = audit_events_run_field_checks(payload)
        if field_errors:
            return None, field_errors
        return engine.create(payload)

    def update_from_form(self, record_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        merged = deepcopy(current)
        merged.update(payload)
        field_errors = audit_events_run_field_checks(merged)
        if field_errors:
            return None, field_errors
        row, errors = engine.update(record_id, payload)
        if row:
            row['_diff'] = audit_events_diff(current, row)
        return row, errors

    def move_status(self, record_id: str, new_status: str) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        errors = audit_events_gate_transition(str(current.get('status') or ''), new_status)
        if errors:
            return None, errors
        return engine.transition(record_id, new_status)

    def export_maps(self) -> list[dict[str, str]]:
        return [audit_events_export_map(row) for row in engine.list_records()]

    def seed_if_empty(self, count: int = 10) -> int:
        return engine.seed_demo(count)


service = AuditEventsService()


def audit_events_safe_payload(form: dict[str, Any]) -> dict[str, Any]:
    allowed = {name for name in ['actor', 'action', 'resource', 'ip_hint', 'occurred_at', 'severity', 'status']}
    clean = {}
    for name, value in form.items():
        if name in allowed or name in {'id', 'status'}:
            clean[name] = value
    return clean


def audit_events_can_delete(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status == 'recorded':
        return True
    return int(row.get('health_score') or 0) < 20


def audit_events_next_statuses(current: str) -> list[str]:
    if current not in ['recorded', 'reviewed', 'escalated', 'closed']:
        return list(['recorded', 'reviewed', 'escalated', 'closed'])
    index = ['recorded', 'reviewed', 'escalated', 'closed'].index(current)
    options = [current]
    if index + 1 < len(['recorded', 'reviewed', 'escalated', 'closed']):
        options.append(['recorded', 'reviewed', 'escalated', 'closed'][index + 1])
    if index > 0:
        options.append(['recorded', 'reviewed', 'escalated', 'closed'][index - 1])
    unique = []
    for item in options:
        if item not in unique:
            unique.append(item)
    return unique


def audit_events_operator_actions(row: dict[str, Any]) -> list[dict[str, str]]:
    actions = [{'code': 'edit', 'label': 'Edit record'}]
    for status in audit_events_next_statuses(str(row.get('status') or '')):
        actions.append({'code': 'status:' + status, 'label': 'Move to ' + status})
    if audit_events_can_delete(row):
        actions.append({'code': 'delete', 'label': 'Remove record'})
    return actions


def audit_events_toast(action: str, ok: bool) -> str:
    if ok:
        return f'Audit Ledger {action} completed.'
    return f'Audit Ledger {action} was blocked by policy.'


def audit_events_dashboard_chip(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'key': 'audit_events',
        'title': 'Audit Ledger',
        'count': len(rows),
        'hot': len([row for row in rows if int(row.get('health_score') or 0) < 45]),
    }

def audit_events_form_help_actor() -> str:
    return 'Enter Actor for Audit Ledger. Local validation runs on save.'


def audit_events_form_help_action() -> str:
    return 'Enter Action for Audit Ledger. Local validation runs on save.'


def audit_events_form_help_resource() -> str:
    return 'Enter Resource for Audit Ledger. Local validation runs on save.'


def audit_events_form_help_ip_hint() -> str:
    return 'Enter Ip Hint for Audit Ledger. Local validation runs on save.'


def audit_events_form_help_occurred_at() -> str:
    return 'Enter Occurred At for Audit Ledger. Local validation runs on save.'


def audit_events_form_help_severity() -> str:
    return 'Enter Severity for Audit Ledger. Local validation runs on save.'


def audit_events_form_help_status() -> str:
    return 'Enter Status for Audit Ledger. Local validation runs on save.'


FORM_HELP_AUDIT_EVENTS = {
    'actor': audit_events_form_help_actor(),
    'action': audit_events_form_help_action(),
    'resource': audit_events_form_help_resource(),
    'ip_hint': audit_events_form_help_ip_hint(),
    'occurred_at': audit_events_form_help_occurred_at(),
    'severity': audit_events_form_help_severity(),
    'status': audit_events_form_help_status(),
}


def audit_events_form_help() -> dict[str, str]:
    return dict(FORM_HELP_AUDIT_EVENTS)

