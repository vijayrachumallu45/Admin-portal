"""Application service for Credit Notes writes and operator actions."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.domains.credit_notes.engine import engine
from app.domains.credit_notes.policies import credit_notes_gate_transition, credit_notes_policy_card, credit_notes_run_field_checks
from app.domains.credit_notes.queries import credit_notes_diff, credit_notes_export_map
from app.domains.credit_notes.reports import build_credit_notes_reporter


class CreditNotesService:
    """Coordinates validation, policy, persistence, and briefings for Credit Notes."""

    def list_view(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        rows = engine.list_records(filters)
        reporter = build_credit_notes_reporter(rows)
        return {
            'rows': rows,
            'kpis': engine.kpi_pack(),
            'pack': reporter.pack(),
        }

    def detail_view(self, record_id: str) -> dict[str, Any] | None:
        row = engine.get(record_id)
        if row is None:
            return None
        card = credit_notes_policy_card(row)
        return {'record': row, 'policy': card}

    def create_from_form(self, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        field_errors = credit_notes_run_field_checks(payload)
        if field_errors:
            return None, field_errors
        return engine.create(payload)

    def update_from_form(self, record_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        merged = deepcopy(current)
        merged.update(payload)
        field_errors = credit_notes_run_field_checks(merged)
        if field_errors:
            return None, field_errors
        row, errors = engine.update(record_id, payload)
        if row:
            row['_diff'] = credit_notes_diff(current, row)
        return row, errors

    def move_status(self, record_id: str, new_status: str) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        errors = credit_notes_gate_transition(str(current.get('status') or ''), new_status)
        if errors:
            return None, errors
        return engine.transition(record_id, new_status)

    def export_maps(self) -> list[dict[str, str]]:
        return [credit_notes_export_map(row) for row in engine.list_records()]

    def seed_if_empty(self, count: int = 10) -> int:
        return engine.seed_demo(count)


service = CreditNotesService()


def credit_notes_safe_payload(form: dict[str, Any]) -> dict[str, Any]:
    allowed = {name for name in ['credit_no', 'invoice_no', 'reason', 'amount_cents', 'approved_by', 'status']}
    clean = {}
    for name, value in form.items():
        if name in allowed or name in {'id', 'status'}:
            clean[name] = value
    return clean


def credit_notes_can_delete(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status == 'draft':
        return True
    return int(row.get('health_score') or 0) < 20


def credit_notes_next_statuses(current: str) -> list[str]:
    if current not in ['draft', 'approved', 'applied', 'rejected']:
        return list(['draft', 'approved', 'applied', 'rejected'])
    index = ['draft', 'approved', 'applied', 'rejected'].index(current)
    options = [current]
    if index + 1 < len(['draft', 'approved', 'applied', 'rejected']):
        options.append(['draft', 'approved', 'applied', 'rejected'][index + 1])
    if index > 0:
        options.append(['draft', 'approved', 'applied', 'rejected'][index - 1])
    unique = []
    for item in options:
        if item not in unique:
            unique.append(item)
    return unique


def credit_notes_operator_actions(row: dict[str, Any]) -> list[dict[str, str]]:
    actions = [{'code': 'edit', 'label': 'Edit record'}]
    for status in credit_notes_next_statuses(str(row.get('status') or '')):
        actions.append({'code': 'status:' + status, 'label': 'Move to ' + status})
    if credit_notes_can_delete(row):
        actions.append({'code': 'delete', 'label': 'Remove record'})
    return actions


def credit_notes_toast(action: str, ok: bool) -> str:
    if ok:
        return f'Credit Notes {action} completed.'
    return f'Credit Notes {action} was blocked by policy.'


def credit_notes_dashboard_chip(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'key': 'credit_notes',
        'title': 'Credit Notes',
        'count': len(rows),
        'hot': len([row for row in rows if int(row.get('health_score') or 0) < 45]),
    }

def credit_notes_form_help_credit_no() -> str:
    return 'Enter Credit No for Credit Notes. Local validation runs on save.'


def credit_notes_form_help_invoice_no() -> str:
    return 'Enter Invoice No for Credit Notes. Local validation runs on save.'


def credit_notes_form_help_reason() -> str:
    return 'Enter Reason for Credit Notes. Local validation runs on save.'


def credit_notes_form_help_amount_cents() -> str:
    return 'Enter Amount Cents for Credit Notes. Local validation runs on save.'


def credit_notes_form_help_approved_by() -> str:
    return 'Enter Approved By for Credit Notes. Local validation runs on save.'


def credit_notes_form_help_status() -> str:
    return 'Enter Status for Credit Notes. Local validation runs on save.'


FORM_HELP_CREDIT_NOTES = {
    'credit_no': credit_notes_form_help_credit_no(),
    'invoice_no': credit_notes_form_help_invoice_no(),
    'reason': credit_notes_form_help_reason(),
    'amount_cents': credit_notes_form_help_amount_cents(),
    'approved_by': credit_notes_form_help_approved_by(),
    'status': credit_notes_form_help_status(),
}


def credit_notes_form_help() -> dict[str, str]:
    return dict(FORM_HELP_CREDIT_NOTES)

