"""Application service for Purchase Orders writes and operator actions."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.domains.purchase_orders.engine import engine
from app.domains.purchase_orders.policies import purchase_orders_gate_transition, purchase_orders_policy_card, purchase_orders_run_field_checks
from app.domains.purchase_orders.queries import purchase_orders_diff, purchase_orders_export_map
from app.domains.purchase_orders.reports import build_purchase_orders_reporter


class PurchaseOrdersService:
    """Coordinates validation, policy, persistence, and briefings for Purchase Orders."""

    def list_view(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        rows = engine.list_records(filters)
        reporter = build_purchase_orders_reporter(rows)
        return {
            'rows': rows,
            'kpis': engine.kpi_pack(),
            'pack': reporter.pack(),
        }

    def detail_view(self, record_id: str) -> dict[str, Any] | None:
        row = engine.get(record_id)
        if row is None:
            return None
        card = purchase_orders_policy_card(row)
        return {'record': row, 'policy': card}

    def create_from_form(self, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        field_errors = purchase_orders_run_field_checks(payload)
        if field_errors:
            return None, field_errors
        return engine.create(payload)

    def update_from_form(self, record_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        merged = deepcopy(current)
        merged.update(payload)
        field_errors = purchase_orders_run_field_checks(merged)
        if field_errors:
            return None, field_errors
        row, errors = engine.update(record_id, payload)
        if row:
            row['_diff'] = purchase_orders_diff(current, row)
        return row, errors

    def move_status(self, record_id: str, new_status: str) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        errors = purchase_orders_gate_transition(str(current.get('status') or ''), new_status)
        if errors:
            return None, errors
        return engine.transition(record_id, new_status)

    def export_maps(self) -> list[dict[str, str]]:
        return [purchase_orders_export_map(row) for row in engine.list_records()]

    def seed_if_empty(self, count: int = 10) -> int:
        return engine.seed_demo(count)


service = PurchaseOrdersService()


def purchase_orders_safe_payload(form: dict[str, Any]) -> dict[str, Any]:
    allowed = {name for name in ['po_number', 'vendor_code', 'budget_code', 'amount_cents', 'needed_by', 'status']}
    clean = {}
    for name, value in form.items():
        if name in allowed or name in {'id', 'status'}:
            clean[name] = value
    return clean


def purchase_orders_can_delete(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status == 'open':
        return True
    return int(row.get('health_score') or 0) < 20


def purchase_orders_next_statuses(current: str) -> list[str]:
    if current not in ['open', 'partial', 'received', 'closed', 'cancelled']:
        return list(['open', 'partial', 'received', 'closed', 'cancelled'])
    index = ['open', 'partial', 'received', 'closed', 'cancelled'].index(current)
    options = [current]
    if index + 1 < len(['open', 'partial', 'received', 'closed', 'cancelled']):
        options.append(['open', 'partial', 'received', 'closed', 'cancelled'][index + 1])
    if index > 0:
        options.append(['open', 'partial', 'received', 'closed', 'cancelled'][index - 1])
    unique = []
    for item in options:
        if item not in unique:
            unique.append(item)
    return unique


def purchase_orders_operator_actions(row: dict[str, Any]) -> list[dict[str, str]]:
    actions = [{'code': 'edit', 'label': 'Edit record'}]
    for status in purchase_orders_next_statuses(str(row.get('status') or '')):
        actions.append({'code': 'status:' + status, 'label': 'Move to ' + status})
    if purchase_orders_can_delete(row):
        actions.append({'code': 'delete', 'label': 'Remove record'})
    return actions


def purchase_orders_toast(action: str, ok: bool) -> str:
    if ok:
        return f'Purchase Orders {action} completed.'
    return f'Purchase Orders {action} was blocked by policy.'


def purchase_orders_dashboard_chip(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'key': 'purchase_orders',
        'title': 'Purchase Orders',
        'count': len(rows),
        'hot': len([row for row in rows if int(row.get('health_score') or 0) < 45]),
    }

def purchase_orders_form_help_po_number() -> str:
    return 'Enter Po Number for Purchase Orders. Local validation runs on save.'


def purchase_orders_form_help_vendor_code() -> str:
    return 'Enter Vendor Code for Purchase Orders. Local validation runs on save.'


def purchase_orders_form_help_budget_code() -> str:
    return 'Enter Budget Code for Purchase Orders. Local validation runs on save.'


def purchase_orders_form_help_amount_cents() -> str:
    return 'Enter Amount Cents for Purchase Orders. Local validation runs on save.'


def purchase_orders_form_help_needed_by() -> str:
    return 'Enter Needed By for Purchase Orders. Local validation runs on save.'


def purchase_orders_form_help_status() -> str:
    return 'Enter Status for Purchase Orders. Local validation runs on save.'


FORM_HELP_PURCHASE_ORDERS = {
    'po_number': purchase_orders_form_help_po_number(),
    'vendor_code': purchase_orders_form_help_vendor_code(),
    'budget_code': purchase_orders_form_help_budget_code(),
    'amount_cents': purchase_orders_form_help_amount_cents(),
    'needed_by': purchase_orders_form_help_needed_by(),
    'status': purchase_orders_form_help_status(),
}


def purchase_orders_form_help() -> dict[str, str]:
    return dict(FORM_HELP_PURCHASE_ORDERS)

