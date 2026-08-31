"""Application service for Invoice Desk writes and operator actions."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.domains.invoices.engine import engine
from app.domains.invoices.policies import invoices_gate_transition, invoices_policy_card, invoices_run_field_checks
from app.domains.invoices.queries import invoices_diff, invoices_export_map
from app.domains.invoices.reports import build_invoices_reporter


class InvoicesService:
    """Coordinates validation, policy, persistence, and briefings for Invoice Desk."""

    def list_view(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        rows = engine.list_records(filters)
        reporter = build_invoices_reporter(rows)
        return {
            'rows': rows,
            'kpis': engine.kpi_pack(),
            'pack': reporter.pack(),
        }

    def detail_view(self, record_id: str) -> dict[str, Any] | None:
        row = engine.get(record_id)
        if row is None:
            return None
        card = invoices_policy_card(row)
        return {'record': row, 'policy': card}

    def create_from_form(self, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        field_errors = invoices_run_field_checks(payload)
        if field_errors:
            return None, field_errors
        return engine.create(payload)

    def update_from_form(self, record_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        merged = deepcopy(current)
        merged.update(payload)
        field_errors = invoices_run_field_checks(merged)
        if field_errors:
            return None, field_errors
        row, errors = engine.update(record_id, payload)
        if row:
            row['_diff'] = invoices_diff(current, row)
        return row, errors

    def move_status(self, record_id: str, new_status: str) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        errors = invoices_gate_transition(str(current.get('status') or ''), new_status)
        if errors:
            return None, errors
        return engine.transition(record_id, new_status)

    def export_maps(self) -> list[dict[str, str]]:
        return [invoices_export_map(row) for row in engine.list_records()]

    def seed_if_empty(self, count: int = 10) -> int:
        return engine.seed_demo(count)


service = InvoicesService()


def invoices_safe_payload(form: dict[str, Any]) -> dict[str, Any]:
    allowed = {name for name in ['invoice_no', 'customer', 'amount_cents', 'currency', 'issued_on', 'due_on', 'status']}
    clean = {}
    for name, value in form.items():
        if name in allowed or name in {'id', 'status'}:
            clean[name] = value
    return clean


def invoices_can_delete(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status == 'draft':
        return True
    return int(row.get('health_score') or 0) < 20


def invoices_next_statuses(current: str) -> list[str]:
    if current not in ['draft', 'sent', 'partial', 'paid', 'void']:
        return list(['draft', 'sent', 'partial', 'paid', 'void'])
    index = ['draft', 'sent', 'partial', 'paid', 'void'].index(current)
    options = [current]
    if index + 1 < len(['draft', 'sent', 'partial', 'paid', 'void']):
        options.append(['draft', 'sent', 'partial', 'paid', 'void'][index + 1])
    if index > 0:
        options.append(['draft', 'sent', 'partial', 'paid', 'void'][index - 1])
    unique = []
    for item in options:
        if item not in unique:
            unique.append(item)
    return unique


def invoices_operator_actions(row: dict[str, Any]) -> list[dict[str, str]]:
    actions = [{'code': 'edit', 'label': 'Edit record'}]
    for status in invoices_next_statuses(str(row.get('status') or '')):
        actions.append({'code': 'status:' + status, 'label': 'Move to ' + status})
    if invoices_can_delete(row):
        actions.append({'code': 'delete', 'label': 'Remove record'})
    return actions


def invoices_toast(action: str, ok: bool) -> str:
    if ok:
        return f'Invoice Desk {action} completed.'
    return f'Invoice Desk {action} was blocked by policy.'


def invoices_dashboard_chip(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'key': 'invoices',
        'title': 'Invoice Desk',
        'count': len(rows),
        'hot': len([row for row in rows if int(row.get('health_score') or 0) < 45]),
    }

def invoices_form_help_invoice_no() -> str:
    return 'Enter Invoice No for Invoice Desk. Local validation runs on save.'


def invoices_form_help_customer() -> str:
    return 'Enter Customer for Invoice Desk. Local validation runs on save.'


def invoices_form_help_amount_cents() -> str:
    return 'Enter Amount Cents for Invoice Desk. Local validation runs on save.'


def invoices_form_help_currency() -> str:
    return 'Enter Currency for Invoice Desk. Local validation runs on save.'


def invoices_form_help_issued_on() -> str:
    return 'Enter Issued On for Invoice Desk. Local validation runs on save.'


def invoices_form_help_due_on() -> str:
    return 'Enter Due On for Invoice Desk. Local validation runs on save.'


def invoices_form_help_status() -> str:
    return 'Enter Status for Invoice Desk. Local validation runs on save.'


FORM_HELP_INVOICES = {
    'invoice_no': invoices_form_help_invoice_no(),
    'customer': invoices_form_help_customer(),
    'amount_cents': invoices_form_help_amount_cents(),
    'currency': invoices_form_help_currency(),
    'issued_on': invoices_form_help_issued_on(),
    'due_on': invoices_form_help_due_on(),
    'status': invoices_form_help_status(),
}


def invoices_form_help() -> dict[str, str]:
    return dict(FORM_HELP_INVOICES)

