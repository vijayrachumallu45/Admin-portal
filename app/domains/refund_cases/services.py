"""Application service for Refund Cases writes and operator actions."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.domains.refund_cases.engine import engine
from app.domains.refund_cases.policies import refund_cases_gate_transition, refund_cases_policy_card, refund_cases_run_field_checks
from app.domains.refund_cases.queries import refund_cases_diff, refund_cases_export_map
from app.domains.refund_cases.reports import build_refund_cases_reporter


class RefundCasesService:
    """Coordinates validation, policy, persistence, and briefings for Refund Cases."""

    def list_view(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        rows = engine.list_records(filters)
        reporter = build_refund_cases_reporter(rows)
        return {
            'rows': rows,
            'kpis': engine.kpi_pack(),
            'pack': reporter.pack(),
        }

    def detail_view(self, record_id: str) -> dict[str, Any] | None:
        row = engine.get(record_id)
        if row is None:
            return None
        card = refund_cases_policy_card(row)
        return {'record': row, 'policy': card}

    def create_from_form(self, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        field_errors = refund_cases_run_field_checks(payload)
        if field_errors:
            return None, field_errors
        return engine.create(payload)

    def update_from_form(self, record_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        merged = deepcopy(current)
        merged.update(payload)
        field_errors = refund_cases_run_field_checks(merged)
        if field_errors:
            return None, field_errors
        row, errors = engine.update(record_id, payload)
        if row:
            row['_diff'] = refund_cases_diff(current, row)
        return row, errors

    def move_status(self, record_id: str, new_status: str) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        errors = refund_cases_gate_transition(str(current.get('status') or ''), new_status)
        if errors:
            return None, errors
        return engine.transition(record_id, new_status)

    def export_maps(self) -> list[dict[str, str]]:
        return [refund_cases_export_map(row) for row in engine.list_records()]

    def seed_if_empty(self, count: int = 10) -> int:
        return engine.seed_demo(count)


service = RefundCasesService()


def refund_cases_safe_payload(form: dict[str, Any]) -> dict[str, Any]:
    allowed = {name for name in ['case_no', 'invoice_no', 'amount_cents', 'reason', 'status']}
    clean = {}
    for name, value in form.items():
        if name in allowed or name in {'id', 'status'}:
            clean[name] = value
    return clean


def refund_cases_can_delete(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status == 'open':
        return True
    return int(row.get('health_score') or 0) < 20


def refund_cases_next_statuses(current: str) -> list[str]:
    if current not in ['open', 'approved', 'issued', 'denied']:
        return list(['open', 'approved', 'issued', 'denied'])
    index = ['open', 'approved', 'issued', 'denied'].index(current)
    options = [current]
    if index + 1 < len(['open', 'approved', 'issued', 'denied']):
        options.append(['open', 'approved', 'issued', 'denied'][index + 1])
    if index > 0:
        options.append(['open', 'approved', 'issued', 'denied'][index - 1])
    unique = []
    for item in options:
        if item not in unique:
            unique.append(item)
    return unique


def refund_cases_operator_actions(row: dict[str, Any]) -> list[dict[str, str]]:
    actions = [{'code': 'edit', 'label': 'Edit record'}]
    for status in refund_cases_next_statuses(str(row.get('status') or '')):
        actions.append({'code': 'status:' + status, 'label': 'Move to ' + status})
    if refund_cases_can_delete(row):
        actions.append({'code': 'delete', 'label': 'Remove record'})
    return actions


def refund_cases_toast(action: str, ok: bool) -> str:
    if ok:
        return f'Refund Cases {action} completed.'
    return f'Refund Cases {action} was blocked by policy.'


def refund_cases_dashboard_chip(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'key': 'refund_cases',
        'title': 'Refund Cases',
        'count': len(rows),
        'hot': len([row for row in rows if int(row.get('health_score') or 0) < 45]),
    }

def refund_cases_form_help_case_no() -> str:
    return 'Enter Case No for Refund Cases. Local validation runs on save.'


def refund_cases_form_help_invoice_no() -> str:
    return 'Enter Invoice No for Refund Cases. Local validation runs on save.'


def refund_cases_form_help_amount_cents() -> str:
    return 'Enter Amount Cents for Refund Cases. Local validation runs on save.'


def refund_cases_form_help_reason() -> str:
    return 'Enter Reason for Refund Cases. Local validation runs on save.'


def refund_cases_form_help_status() -> str:
    return 'Enter Status for Refund Cases. Local validation runs on save.'


FORM_HELP_REFUND_CASES = {
    'case_no': refund_cases_form_help_case_no(),
    'invoice_no': refund_cases_form_help_invoice_no(),
    'amount_cents': refund_cases_form_help_amount_cents(),
    'reason': refund_cases_form_help_reason(),
    'status': refund_cases_form_help_status(),
}


def refund_cases_form_help() -> dict[str, str]:
    return dict(FORM_HELP_REFUND_CASES)

