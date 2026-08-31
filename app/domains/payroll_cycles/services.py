"""Application service for Payroll Cycles writes and operator actions."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.domains.payroll_cycles.engine import engine
from app.domains.payroll_cycles.policies import payroll_cycles_gate_transition, payroll_cycles_policy_card, payroll_cycles_run_field_checks
from app.domains.payroll_cycles.queries import payroll_cycles_diff, payroll_cycles_export_map
from app.domains.payroll_cycles.reports import build_payroll_cycles_reporter


class PayrollCyclesService:
    """Coordinates validation, policy, persistence, and briefings for Payroll Cycles."""

    def list_view(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        rows = engine.list_records(filters)
        reporter = build_payroll_cycles_reporter(rows)
        return {
            'rows': rows,
            'kpis': engine.kpi_pack(),
            'pack': reporter.pack(),
        }

    def detail_view(self, record_id: str) -> dict[str, Any] | None:
        row = engine.get(record_id)
        if row is None:
            return None
        card = payroll_cycles_policy_card(row)
        return {'record': row, 'policy': card}

    def create_from_form(self, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        field_errors = payroll_cycles_run_field_checks(payload)
        if field_errors:
            return None, field_errors
        return engine.create(payload)

    def update_from_form(self, record_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        merged = deepcopy(current)
        merged.update(payload)
        field_errors = payroll_cycles_run_field_checks(merged)
        if field_errors:
            return None, field_errors
        row, errors = engine.update(record_id, payload)
        if row:
            row['_diff'] = payroll_cycles_diff(current, row)
        return row, errors

    def move_status(self, record_id: str, new_status: str) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        errors = payroll_cycles_gate_transition(str(current.get('status') or ''), new_status)
        if errors:
            return None, errors
        return engine.transition(record_id, new_status)

    def export_maps(self) -> list[dict[str, str]]:
        return [payroll_cycles_export_map(row) for row in engine.list_records()]

    def seed_if_empty(self, count: int = 10) -> int:
        return engine.seed_demo(count)


service = PayrollCyclesService()


def payroll_cycles_safe_payload(form: dict[str, Any]) -> dict[str, Any]:
    allowed = {name for name in ['cycle_code', 'period', 'lock_on', 'processor', 'status']}
    clean = {}
    for name, value in form.items():
        if name in allowed or name in {'id', 'status'}:
            clean[name] = value
    return clean


def payroll_cycles_can_delete(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status == 'open':
        return True
    return int(row.get('health_score') or 0) < 20


def payroll_cycles_next_statuses(current: str) -> list[str]:
    if current not in ['open', 'locked', 'paid']:
        return list(['open', 'locked', 'paid'])
    index = ['open', 'locked', 'paid'].index(current)
    options = [current]
    if index + 1 < len(['open', 'locked', 'paid']):
        options.append(['open', 'locked', 'paid'][index + 1])
    if index > 0:
        options.append(['open', 'locked', 'paid'][index - 1])
    unique = []
    for item in options:
        if item not in unique:
            unique.append(item)
    return unique


def payroll_cycles_operator_actions(row: dict[str, Any]) -> list[dict[str, str]]:
    actions = [{'code': 'edit', 'label': 'Edit record'}]
    for status in payroll_cycles_next_statuses(str(row.get('status') or '')):
        actions.append({'code': 'status:' + status, 'label': 'Move to ' + status})
    if payroll_cycles_can_delete(row):
        actions.append({'code': 'delete', 'label': 'Remove record'})
    return actions


def payroll_cycles_toast(action: str, ok: bool) -> str:
    if ok:
        return f'Payroll Cycles {action} completed.'
    return f'Payroll Cycles {action} was blocked by policy.'


def payroll_cycles_dashboard_chip(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'key': 'payroll_cycles',
        'title': 'Payroll Cycles',
        'count': len(rows),
        'hot': len([row for row in rows if int(row.get('health_score') or 0) < 45]),
    }

def payroll_cycles_form_help_cycle_code() -> str:
    return 'Enter Cycle Code for Payroll Cycles. Local validation runs on save.'


def payroll_cycles_form_help_period() -> str:
    return 'Enter Period for Payroll Cycles. Local validation runs on save.'


def payroll_cycles_form_help_lock_on() -> str:
    return 'Enter Lock On for Payroll Cycles. Local validation runs on save.'


def payroll_cycles_form_help_processor() -> str:
    return 'Enter Processor for Payroll Cycles. Local validation runs on save.'


def payroll_cycles_form_help_status() -> str:
    return 'Enter Status for Payroll Cycles. Local validation runs on save.'


FORM_HELP_PAYROLL_CYCLES = {
    'cycle_code': payroll_cycles_form_help_cycle_code(),
    'period': payroll_cycles_form_help_period(),
    'lock_on': payroll_cycles_form_help_lock_on(),
    'processor': payroll_cycles_form_help_processor(),
    'status': payroll_cycles_form_help_status(),
}


def payroll_cycles_form_help() -> dict[str, str]:
    return dict(FORM_HELP_PAYROLL_CYCLES)

