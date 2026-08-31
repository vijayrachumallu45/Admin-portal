"""Application service for Vendor Register writes and operator actions."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.domains.vendors.engine import engine
from app.domains.vendors.policies import vendors_gate_transition, vendors_policy_card, vendors_run_field_checks
from app.domains.vendors.queries import vendors_diff, vendors_export_map
from app.domains.vendors.reports import build_vendors_reporter


class VendorsService:
    """Coordinates validation, policy, persistence, and briefings for Vendor Register."""

    def list_view(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        rows = engine.list_records(filters)
        reporter = build_vendors_reporter(rows)
        return {
            'rows': rows,
            'kpis': engine.kpi_pack(),
            'pack': reporter.pack(),
        }

    def detail_view(self, record_id: str) -> dict[str, Any] | None:
        row = engine.get(record_id)
        if row is None:
            return None
        card = vendors_policy_card(row)
        return {'record': row, 'policy': card}

    def create_from_form(self, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        field_errors = vendors_run_field_checks(payload)
        if field_errors:
            return None, field_errors
        return engine.create(payload)

    def update_from_form(self, record_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        merged = deepcopy(current)
        merged.update(payload)
        field_errors = vendors_run_field_checks(merged)
        if field_errors:
            return None, field_errors
        row, errors = engine.update(record_id, payload)
        if row:
            row['_diff'] = vendors_diff(current, row)
        return row, errors

    def move_status(self, record_id: str, new_status: str) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        errors = vendors_gate_transition(str(current.get('status') or ''), new_status)
        if errors:
            return None, errors
        return engine.transition(record_id, new_status)

    def export_maps(self) -> list[dict[str, str]]:
        return [vendors_export_map(row) for row in engine.list_records()]

    def seed_if_empty(self, count: int = 10) -> int:
        return engine.seed_demo(count)


service = VendorsService()


def vendors_safe_payload(form: dict[str, Any]) -> dict[str, Any]:
    allowed = {name for name in ['vendor_code', 'name', 'category', 'country', 'risk_score', 'status']}
    clean = {}
    for name, value in form.items():
        if name in allowed or name in {'id', 'status'}:
            clean[name] = value
    return clean


def vendors_can_delete(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status == 'screening':
        return True
    return int(row.get('health_score') or 0) < 20


def vendors_next_statuses(current: str) -> list[str]:
    if current not in ['screening', 'approved', 'watchlist', 'exited']:
        return list(['screening', 'approved', 'watchlist', 'exited'])
    index = ['screening', 'approved', 'watchlist', 'exited'].index(current)
    options = [current]
    if index + 1 < len(['screening', 'approved', 'watchlist', 'exited']):
        options.append(['screening', 'approved', 'watchlist', 'exited'][index + 1])
    if index > 0:
        options.append(['screening', 'approved', 'watchlist', 'exited'][index - 1])
    unique = []
    for item in options:
        if item not in unique:
            unique.append(item)
    return unique


def vendors_operator_actions(row: dict[str, Any]) -> list[dict[str, str]]:
    actions = [{'code': 'edit', 'label': 'Edit record'}]
    for status in vendors_next_statuses(str(row.get('status') or '')):
        actions.append({'code': 'status:' + status, 'label': 'Move to ' + status})
    if vendors_can_delete(row):
        actions.append({'code': 'delete', 'label': 'Remove record'})
    return actions


def vendors_toast(action: str, ok: bool) -> str:
    if ok:
        return f'Vendor Register {action} completed.'
    return f'Vendor Register {action} was blocked by policy.'


def vendors_dashboard_chip(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'key': 'vendors',
        'title': 'Vendor Register',
        'count': len(rows),
        'hot': len([row for row in rows if int(row.get('health_score') or 0) < 45]),
    }

def vendors_form_help_vendor_code() -> str:
    return 'Enter Vendor Code for Vendor Register. Local validation runs on save.'


def vendors_form_help_name() -> str:
    return 'Enter Name for Vendor Register. Local validation runs on save.'


def vendors_form_help_category() -> str:
    return 'Enter Category for Vendor Register. Local validation runs on save.'


def vendors_form_help_country() -> str:
    return 'Enter Country for Vendor Register. Local validation runs on save.'


def vendors_form_help_risk_score() -> str:
    return 'Enter Risk Score for Vendor Register. Local validation runs on save.'


def vendors_form_help_status() -> str:
    return 'Enter Status for Vendor Register. Local validation runs on save.'


FORM_HELP_VENDORS = {
    'vendor_code': vendors_form_help_vendor_code(),
    'name': vendors_form_help_name(),
    'category': vendors_form_help_category(),
    'country': vendors_form_help_country(),
    'risk_score': vendors_form_help_risk_score(),
    'status': vendors_form_help_status(),
}


def vendors_form_help() -> dict[str, str]:
    return dict(FORM_HELP_VENDORS)

