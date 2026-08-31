"""Application service for Contract Vault writes and operator actions."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.domains.contracts.engine import engine
from app.domains.contracts.policies import contracts_gate_transition, contracts_policy_card, contracts_run_field_checks
from app.domains.contracts.queries import contracts_diff, contracts_export_map
from app.domains.contracts.reports import build_contracts_reporter


class ContractsService:
    """Coordinates validation, policy, persistence, and briefings for Contract Vault."""

    def list_view(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        rows = engine.list_records(filters)
        reporter = build_contracts_reporter(rows)
        return {
            'rows': rows,
            'kpis': engine.kpi_pack(),
            'pack': reporter.pack(),
        }

    def detail_view(self, record_id: str) -> dict[str, Any] | None:
        row = engine.get(record_id)
        if row is None:
            return None
        card = contracts_policy_card(row)
        return {'record': row, 'policy': card}

    def create_from_form(self, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        field_errors = contracts_run_field_checks(payload)
        if field_errors:
            return None, field_errors
        return engine.create(payload)

    def update_from_form(self, record_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        merged = deepcopy(current)
        merged.update(payload)
        field_errors = contracts_run_field_checks(merged)
        if field_errors:
            return None, field_errors
        row, errors = engine.update(record_id, payload)
        if row:
            row['_diff'] = contracts_diff(current, row)
        return row, errors

    def move_status(self, record_id: str, new_status: str) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        errors = contracts_gate_transition(str(current.get('status') or ''), new_status)
        if errors:
            return None, errors
        return engine.transition(record_id, new_status)

    def export_maps(self) -> list[dict[str, str]]:
        return [contracts_export_map(row) for row in engine.list_records()]

    def seed_if_empty(self, count: int = 10) -> int:
        return engine.seed_demo(count)


service = ContractsService()


def contracts_safe_payload(form: dict[str, Any]) -> dict[str, Any]:
    allowed = {name for name in ['contract_no', 'counterparty', 'value_cents', 'renew_on', 'legal_owner', 'status']}
    clean = {}
    for name, value in form.items():
        if name in allowed or name in {'id', 'status'}:
            clean[name] = value
    return clean


def contracts_can_delete(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status == 'negotiation':
        return True
    return int(row.get('health_score') or 0) < 20


def contracts_next_statuses(current: str) -> list[str]:
    if current not in ['negotiation', 'signed', 'renewing', 'expired']:
        return list(['negotiation', 'signed', 'renewing', 'expired'])
    index = ['negotiation', 'signed', 'renewing', 'expired'].index(current)
    options = [current]
    if index + 1 < len(['negotiation', 'signed', 'renewing', 'expired']):
        options.append(['negotiation', 'signed', 'renewing', 'expired'][index + 1])
    if index > 0:
        options.append(['negotiation', 'signed', 'renewing', 'expired'][index - 1])
    unique = []
    for item in options:
        if item not in unique:
            unique.append(item)
    return unique


def contracts_operator_actions(row: dict[str, Any]) -> list[dict[str, str]]:
    actions = [{'code': 'edit', 'label': 'Edit record'}]
    for status in contracts_next_statuses(str(row.get('status') or '')):
        actions.append({'code': 'status:' + status, 'label': 'Move to ' + status})
    if contracts_can_delete(row):
        actions.append({'code': 'delete', 'label': 'Remove record'})
    return actions


def contracts_toast(action: str, ok: bool) -> str:
    if ok:
        return f'Contract Vault {action} completed.'
    return f'Contract Vault {action} was blocked by policy.'


def contracts_dashboard_chip(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'key': 'contracts',
        'title': 'Contract Vault',
        'count': len(rows),
        'hot': len([row for row in rows if int(row.get('health_score') or 0) < 45]),
    }

def contracts_form_help_contract_no() -> str:
    return 'Enter Contract No for Contract Vault. Local validation runs on save.'


def contracts_form_help_counterparty() -> str:
    return 'Enter Counterparty for Contract Vault. Local validation runs on save.'


def contracts_form_help_value_cents() -> str:
    return 'Enter Value Cents for Contract Vault. Local validation runs on save.'


def contracts_form_help_renew_on() -> str:
    return 'Enter Renew On for Contract Vault. Local validation runs on save.'


def contracts_form_help_legal_owner() -> str:
    return 'Enter Legal Owner for Contract Vault. Local validation runs on save.'


def contracts_form_help_status() -> str:
    return 'Enter Status for Contract Vault. Local validation runs on save.'


FORM_HELP_CONTRACTS = {
    'contract_no': contracts_form_help_contract_no(),
    'counterparty': contracts_form_help_counterparty(),
    'value_cents': contracts_form_help_value_cents(),
    'renew_on': contracts_form_help_renew_on(),
    'legal_owner': contracts_form_help_legal_owner(),
    'status': contracts_form_help_status(),
}


def contracts_form_help() -> dict[str, str]:
    return dict(FORM_HELP_CONTRACTS)

