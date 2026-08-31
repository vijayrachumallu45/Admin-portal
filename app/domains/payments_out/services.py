"""Application service for Outbound Payments writes and operator actions."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.domains.payments_out.engine import engine
from app.domains.payments_out.policies import payments_out_gate_transition, payments_out_policy_card, payments_out_run_field_checks
from app.domains.payments_out.queries import payments_out_diff, payments_out_export_map
from app.domains.payments_out.reports import build_payments_out_reporter


class PaymentsOutService:
    """Coordinates validation, policy, persistence, and briefings for Outbound Payments."""

    def list_view(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        rows = engine.list_records(filters)
        reporter = build_payments_out_reporter(rows)
        return {
            'rows': rows,
            'kpis': engine.kpi_pack(),
            'pack': reporter.pack(),
        }

    def detail_view(self, record_id: str) -> dict[str, Any] | None:
        row = engine.get(record_id)
        if row is None:
            return None
        card = payments_out_policy_card(row)
        return {'record': row, 'policy': card}

    def create_from_form(self, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        field_errors = payments_out_run_field_checks(payload)
        if field_errors:
            return None, field_errors
        return engine.create(payload)

    def update_from_form(self, record_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        merged = deepcopy(current)
        merged.update(payload)
        field_errors = payments_out_run_field_checks(merged)
        if field_errors:
            return None, field_errors
        row, errors = engine.update(record_id, payload)
        if row:
            row['_diff'] = payments_out_diff(current, row)
        return row, errors

    def move_status(self, record_id: str, new_status: str) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        errors = payments_out_gate_transition(str(current.get('status') or ''), new_status)
        if errors:
            return None, errors
        return engine.transition(record_id, new_status)

    def export_maps(self) -> list[dict[str, str]]:
        return [payments_out_export_map(row) for row in engine.list_records()]

    def seed_if_empty(self, count: int = 10) -> int:
        return engine.seed_demo(count)


service = PaymentsOutService()


def payments_out_safe_payload(form: dict[str, Any]) -> dict[str, Any]:
    allowed = {name for name in ['payment_no', 'payee', 'amount_cents', 'method', 'paid_on', 'status']}
    clean = {}
    for name, value in form.items():
        if name in allowed or name in {'id', 'status'}:
            clean[name] = value
    return clean


def payments_out_can_delete(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status == 'queued':
        return True
    return int(row.get('health_score') or 0) < 20


def payments_out_next_statuses(current: str) -> list[str]:
    if current not in ['queued', 'approved', 'sent', 'failed', 'void']:
        return list(['queued', 'approved', 'sent', 'failed', 'void'])
    index = ['queued', 'approved', 'sent', 'failed', 'void'].index(current)
    options = [current]
    if index + 1 < len(['queued', 'approved', 'sent', 'failed', 'void']):
        options.append(['queued', 'approved', 'sent', 'failed', 'void'][index + 1])
    if index > 0:
        options.append(['queued', 'approved', 'sent', 'failed', 'void'][index - 1])
    unique = []
    for item in options:
        if item not in unique:
            unique.append(item)
    return unique


def payments_out_operator_actions(row: dict[str, Any]) -> list[dict[str, str]]:
    actions = [{'code': 'edit', 'label': 'Edit record'}]
    for status in payments_out_next_statuses(str(row.get('status') or '')):
        actions.append({'code': 'status:' + status, 'label': 'Move to ' + status})
    if payments_out_can_delete(row):
        actions.append({'code': 'delete', 'label': 'Remove record'})
    return actions


def payments_out_toast(action: str, ok: bool) -> str:
    if ok:
        return f'Outbound Payments {action} completed.'
    return f'Outbound Payments {action} was blocked by policy.'


def payments_out_dashboard_chip(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'key': 'payments_out',
        'title': 'Outbound Payments',
        'count': len(rows),
        'hot': len([row for row in rows if int(row.get('health_score') or 0) < 45]),
    }

def payments_out_form_help_payment_no() -> str:
    return 'Enter Payment No for Outbound Payments. Local validation runs on save.'


def payments_out_form_help_payee() -> str:
    return 'Enter Payee for Outbound Payments. Local validation runs on save.'


def payments_out_form_help_amount_cents() -> str:
    return 'Enter Amount Cents for Outbound Payments. Local validation runs on save.'


def payments_out_form_help_method() -> str:
    return 'Enter Method for Outbound Payments. Local validation runs on save.'


def payments_out_form_help_paid_on() -> str:
    return 'Enter Paid On for Outbound Payments. Local validation runs on save.'


def payments_out_form_help_status() -> str:
    return 'Enter Status for Outbound Payments. Local validation runs on save.'


FORM_HELP_PAYMENTS_OUT = {
    'payment_no': payments_out_form_help_payment_no(),
    'payee': payments_out_form_help_payee(),
    'amount_cents': payments_out_form_help_amount_cents(),
    'method': payments_out_form_help_method(),
    'paid_on': payments_out_form_help_paid_on(),
    'status': payments_out_form_help_status(),
}


def payments_out_form_help() -> dict[str, str]:
    return dict(FORM_HELP_PAYMENTS_OUT)

