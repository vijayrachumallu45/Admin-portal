"""Application service for Support Queue writes and operator actions."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.domains.support_tickets.engine import engine
from app.domains.support_tickets.policies import support_tickets_gate_transition, support_tickets_policy_card, support_tickets_run_field_checks
from app.domains.support_tickets.queries import support_tickets_diff, support_tickets_export_map
from app.domains.support_tickets.reports import build_support_tickets_reporter


class SupportTicketsService:
    """Coordinates validation, policy, persistence, and briefings for Support Queue."""

    def list_view(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        rows = engine.list_records(filters)
        reporter = build_support_tickets_reporter(rows)
        return {
            'rows': rows,
            'kpis': engine.kpi_pack(),
            'pack': reporter.pack(),
        }

    def detail_view(self, record_id: str) -> dict[str, Any] | None:
        row = engine.get(record_id)
        if row is None:
            return None
        card = support_tickets_policy_card(row)
        return {'record': row, 'policy': card}

    def create_from_form(self, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        field_errors = support_tickets_run_field_checks(payload)
        if field_errors:
            return None, field_errors
        return engine.create(payload)

    def update_from_form(self, record_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        merged = deepcopy(current)
        merged.update(payload)
        field_errors = support_tickets_run_field_checks(merged)
        if field_errors:
            return None, field_errors
        row, errors = engine.update(record_id, payload)
        if row:
            row['_diff'] = support_tickets_diff(current, row)
        return row, errors

    def move_status(self, record_id: str, new_status: str) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        errors = support_tickets_gate_transition(str(current.get('status') or ''), new_status)
        if errors:
            return None, errors
        return engine.transition(record_id, new_status)

    def export_maps(self) -> list[dict[str, str]]:
        return [support_tickets_export_map(row) for row in engine.list_records()]

    def seed_if_empty(self, count: int = 10) -> int:
        return engine.seed_demo(count)


service = SupportTicketsService()


def support_tickets_safe_payload(form: dict[str, Any]) -> dict[str, Any]:
    allowed = {name for name in ['ticket_no', 'subject', 'severity', 'requester', 'assignee', 'status']}
    clean = {}
    for name, value in form.items():
        if name in allowed or name in {'id', 'status'}:
            clean[name] = value
    return clean


def support_tickets_can_delete(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status == 'new':
        return True
    return int(row.get('health_score') or 0) < 20


def support_tickets_next_statuses(current: str) -> list[str]:
    if current not in ['new', 'open', 'pending', 'resolved', 'closed']:
        return list(['new', 'open', 'pending', 'resolved', 'closed'])
    index = ['new', 'open', 'pending', 'resolved', 'closed'].index(current)
    options = [current]
    if index + 1 < len(['new', 'open', 'pending', 'resolved', 'closed']):
        options.append(['new', 'open', 'pending', 'resolved', 'closed'][index + 1])
    if index > 0:
        options.append(['new', 'open', 'pending', 'resolved', 'closed'][index - 1])
    unique = []
    for item in options:
        if item not in unique:
            unique.append(item)
    return unique


def support_tickets_operator_actions(row: dict[str, Any]) -> list[dict[str, str]]:
    actions = [{'code': 'edit', 'label': 'Edit record'}]
    for status in support_tickets_next_statuses(str(row.get('status') or '')):
        actions.append({'code': 'status:' + status, 'label': 'Move to ' + status})
    if support_tickets_can_delete(row):
        actions.append({'code': 'delete', 'label': 'Remove record'})
    return actions


def support_tickets_toast(action: str, ok: bool) -> str:
    if ok:
        return f'Support Queue {action} completed.'
    return f'Support Queue {action} was blocked by policy.'


def support_tickets_dashboard_chip(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'key': 'support_tickets',
        'title': 'Support Queue',
        'count': len(rows),
        'hot': len([row for row in rows if int(row.get('health_score') or 0) < 45]),
    }

def support_tickets_form_help_ticket_no() -> str:
    return 'Enter Ticket No for Support Queue. Local validation runs on save.'


def support_tickets_form_help_subject() -> str:
    return 'Enter Subject for Support Queue. Local validation runs on save.'


def support_tickets_form_help_severity() -> str:
    return 'Enter Severity for Support Queue. Local validation runs on save.'


def support_tickets_form_help_requester() -> str:
    return 'Enter Requester for Support Queue. Local validation runs on save.'


def support_tickets_form_help_assignee() -> str:
    return 'Enter Assignee for Support Queue. Local validation runs on save.'


def support_tickets_form_help_status() -> str:
    return 'Enter Status for Support Queue. Local validation runs on save.'


FORM_HELP_SUPPORT_TICKETS = {
    'ticket_no': support_tickets_form_help_ticket_no(),
    'subject': support_tickets_form_help_subject(),
    'severity': support_tickets_form_help_severity(),
    'requester': support_tickets_form_help_requester(),
    'assignee': support_tickets_form_help_assignee(),
    'status': support_tickets_form_help_status(),
}


def support_tickets_form_help() -> dict[str, str]:
    return dict(FORM_HELP_SUPPORT_TICKETS)

