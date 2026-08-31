"""Application service for Tenant Directory writes and operator actions."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.domains.tenants.engine import engine
from app.domains.tenants.policies import tenants_gate_transition, tenants_policy_card, tenants_run_field_checks
from app.domains.tenants.queries import tenants_diff, tenants_export_map
from app.domains.tenants.reports import build_tenants_reporter


class TenantsService:
    """Coordinates validation, policy, persistence, and briefings for Tenant Directory."""

    def list_view(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        rows = engine.list_records(filters)
        reporter = build_tenants_reporter(rows)
        return {
            'rows': rows,
            'kpis': engine.kpi_pack(),
            'pack': reporter.pack(),
        }

    def detail_view(self, record_id: str) -> dict[str, Any] | None:
        row = engine.get(record_id)
        if row is None:
            return None
        card = tenants_policy_card(row)
        return {'record': row, 'policy': card}

    def create_from_form(self, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        field_errors = tenants_run_field_checks(payload)
        if field_errors:
            return None, field_errors
        return engine.create(payload)

    def update_from_form(self, record_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        merged = deepcopy(current)
        merged.update(payload)
        field_errors = tenants_run_field_checks(merged)
        if field_errors:
            return None, field_errors
        row, errors = engine.update(record_id, payload)
        if row:
            row['_diff'] = tenants_diff(current, row)
        return row, errors

    def move_status(self, record_id: str, new_status: str) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        errors = tenants_gate_transition(str(current.get('status') or ''), new_status)
        if errors:
            return None, errors
        return engine.transition(record_id, new_status)

    def export_maps(self) -> list[dict[str, str]]:
        return [tenants_export_map(row) for row in engine.list_records()]

    def seed_if_empty(self, count: int = 10) -> int:
        return engine.seed_demo(count)


service = TenantsService()


def tenants_safe_payload(form: dict[str, Any]) -> dict[str, Any]:
    allowed = {name for name in ['code', 'legal_name', 'region', 'tier', 'seat_limit', 'mrr_cents', 'go_live', 'status']}
    clean = {}
    for name, value in form.items():
        if name in allowed or name in {'id', 'status'}:
            clean[name] = value
    return clean


def tenants_can_delete(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status == 'prospect':
        return True
    return int(row.get('health_score') or 0) < 20


def tenants_next_statuses(current: str) -> list[str]:
    if current not in ['prospect', 'onboarding', 'live', 'suspended', 'churned']:
        return list(['prospect', 'onboarding', 'live', 'suspended', 'churned'])
    index = ['prospect', 'onboarding', 'live', 'suspended', 'churned'].index(current)
    options = [current]
    if index + 1 < len(['prospect', 'onboarding', 'live', 'suspended', 'churned']):
        options.append(['prospect', 'onboarding', 'live', 'suspended', 'churned'][index + 1])
    if index > 0:
        options.append(['prospect', 'onboarding', 'live', 'suspended', 'churned'][index - 1])
    unique = []
    for item in options:
        if item not in unique:
            unique.append(item)
    return unique


def tenants_operator_actions(row: dict[str, Any]) -> list[dict[str, str]]:
    actions = [{'code': 'edit', 'label': 'Edit record'}]
    for status in tenants_next_statuses(str(row.get('status') or '')):
        actions.append({'code': 'status:' + status, 'label': 'Move to ' + status})
    if tenants_can_delete(row):
        actions.append({'code': 'delete', 'label': 'Remove record'})
    return actions


def tenants_toast(action: str, ok: bool) -> str:
    if ok:
        return f'Tenant Directory {action} completed.'
    return f'Tenant Directory {action} was blocked by policy.'


def tenants_dashboard_chip(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'key': 'tenants',
        'title': 'Tenant Directory',
        'count': len(rows),
        'hot': len([row for row in rows if int(row.get('health_score') or 0) < 45]),
    }

def tenants_form_help_code() -> str:
    return 'Enter Code for Tenant Directory. Local validation runs on save.'


def tenants_form_help_legal_name() -> str:
    return 'Enter Legal Name for Tenant Directory. Local validation runs on save.'


def tenants_form_help_region() -> str:
    return 'Enter Region for Tenant Directory. Local validation runs on save.'


def tenants_form_help_tier() -> str:
    return 'Enter Tier for Tenant Directory. Local validation runs on save.'


def tenants_form_help_seat_limit() -> str:
    return 'Enter Seat Limit for Tenant Directory. Local validation runs on save.'


def tenants_form_help_mrr_cents() -> str:
    return 'Enter Mrr Cents for Tenant Directory. Local validation runs on save.'


def tenants_form_help_go_live() -> str:
    return 'Enter Go Live for Tenant Directory. Local validation runs on save.'


def tenants_form_help_status() -> str:
    return 'Enter Status for Tenant Directory. Local validation runs on save.'


FORM_HELP_TENANTS = {
    'code': tenants_form_help_code(),
    'legal_name': tenants_form_help_legal_name(),
    'region': tenants_form_help_region(),
    'tier': tenants_form_help_tier(),
    'seat_limit': tenants_form_help_seat_limit(),
    'mrr_cents': tenants_form_help_mrr_cents(),
    'go_live': tenants_form_help_go_live(),
    'status': tenants_form_help_status(),
}


def tenants_form_help() -> dict[str, str]:
    return dict(FORM_HELP_TENANTS)

