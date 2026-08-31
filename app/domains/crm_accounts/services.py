"""Application service for CRM Accounts writes and operator actions."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.domains.crm_accounts.engine import engine
from app.domains.crm_accounts.policies import crm_accounts_gate_transition, crm_accounts_policy_card, crm_accounts_run_field_checks
from app.domains.crm_accounts.queries import crm_accounts_diff, crm_accounts_export_map
from app.domains.crm_accounts.reports import build_crm_accounts_reporter


class CrmAccountsService:
    """Coordinates validation, policy, persistence, and briefings for CRM Accounts."""

    def list_view(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        rows = engine.list_records(filters)
        reporter = build_crm_accounts_reporter(rows)
        return {
            'rows': rows,
            'kpis': engine.kpi_pack(),
            'pack': reporter.pack(),
        }

    def detail_view(self, record_id: str) -> dict[str, Any] | None:
        row = engine.get(record_id)
        if row is None:
            return None
        card = crm_accounts_policy_card(row)
        return {'record': row, 'policy': card}

    def create_from_form(self, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        field_errors = crm_accounts_run_field_checks(payload)
        if field_errors:
            return None, field_errors
        return engine.create(payload)

    def update_from_form(self, record_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        merged = deepcopy(current)
        merged.update(payload)
        field_errors = crm_accounts_run_field_checks(merged)
        if field_errors:
            return None, field_errors
        row, errors = engine.update(record_id, payload)
        if row:
            row['_diff'] = crm_accounts_diff(current, row)
        return row, errors

    def move_status(self, record_id: str, new_status: str) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        errors = crm_accounts_gate_transition(str(current.get('status') or ''), new_status)
        if errors:
            return None, errors
        return engine.transition(record_id, new_status)

    def export_maps(self) -> list[dict[str, str]]:
        return [crm_accounts_export_map(row) for row in engine.list_records()]

    def seed_if_empty(self, count: int = 10) -> int:
        return engine.seed_demo(count)


service = CrmAccountsService()


def crm_accounts_safe_payload(form: dict[str, Any]) -> dict[str, Any]:
    allowed = {name for name in ['account_name', 'segment', 'owner', 'industry', 'employees', 'status']}
    clean = {}
    for name, value in form.items():
        if name in allowed or name in {'id', 'status'}:
            clean[name] = value
    return clean


def crm_accounts_can_delete(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status == 'prospect':
        return True
    return int(row.get('health_score') or 0) < 20


def crm_accounts_next_statuses(current: str) -> list[str]:
    if current not in ['prospect', 'customer', 'partner', 'inactive']:
        return list(['prospect', 'customer', 'partner', 'inactive'])
    index = ['prospect', 'customer', 'partner', 'inactive'].index(current)
    options = [current]
    if index + 1 < len(['prospect', 'customer', 'partner', 'inactive']):
        options.append(['prospect', 'customer', 'partner', 'inactive'][index + 1])
    if index > 0:
        options.append(['prospect', 'customer', 'partner', 'inactive'][index - 1])
    unique = []
    for item in options:
        if item not in unique:
            unique.append(item)
    return unique


def crm_accounts_operator_actions(row: dict[str, Any]) -> list[dict[str, str]]:
    actions = [{'code': 'edit', 'label': 'Edit record'}]
    for status in crm_accounts_next_statuses(str(row.get('status') or '')):
        actions.append({'code': 'status:' + status, 'label': 'Move to ' + status})
    if crm_accounts_can_delete(row):
        actions.append({'code': 'delete', 'label': 'Remove record'})
    return actions


def crm_accounts_toast(action: str, ok: bool) -> str:
    if ok:
        return f'CRM Accounts {action} completed.'
    return f'CRM Accounts {action} was blocked by policy.'


def crm_accounts_dashboard_chip(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'key': 'crm_accounts',
        'title': 'CRM Accounts',
        'count': len(rows),
        'hot': len([row for row in rows if int(row.get('health_score') or 0) < 45]),
    }

def crm_accounts_form_help_account_name() -> str:
    return 'Enter Account Name for CRM Accounts. Local validation runs on save.'


def crm_accounts_form_help_segment() -> str:
    return 'Enter Segment for CRM Accounts. Local validation runs on save.'


def crm_accounts_form_help_owner() -> str:
    return 'Enter Owner for CRM Accounts. Local validation runs on save.'


def crm_accounts_form_help_industry() -> str:
    return 'Enter Industry for CRM Accounts. Local validation runs on save.'


def crm_accounts_form_help_employees() -> str:
    return 'Enter Employees for CRM Accounts. Local validation runs on save.'


def crm_accounts_form_help_status() -> str:
    return 'Enter Status for CRM Accounts. Local validation runs on save.'


FORM_HELP_CRM_ACCOUNTS = {
    'account_name': crm_accounts_form_help_account_name(),
    'segment': crm_accounts_form_help_segment(),
    'owner': crm_accounts_form_help_owner(),
    'industry': crm_accounts_form_help_industry(),
    'employees': crm_accounts_form_help_employees(),
    'status': crm_accounts_form_help_status(),
}


def crm_accounts_form_help() -> dict[str, str]:
    return dict(FORM_HELP_CRM_ACCOUNTS)

