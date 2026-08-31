"""Application service for Access Grants writes and operator actions."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.domains.access_grants.engine import engine
from app.domains.access_grants.policies import access_grants_gate_transition, access_grants_policy_card, access_grants_run_field_checks
from app.domains.access_grants.queries import access_grants_diff, access_grants_export_map
from app.domains.access_grants.reports import build_access_grants_reporter


class AccessGrantsService:
    """Coordinates validation, policy, persistence, and briefings for Access Grants."""

    def list_view(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        rows = engine.list_records(filters)
        reporter = build_access_grants_reporter(rows)
        return {
            'rows': rows,
            'kpis': engine.kpi_pack(),
            'pack': reporter.pack(),
        }

    def detail_view(self, record_id: str) -> dict[str, Any] | None:
        row = engine.get(record_id)
        if row is None:
            return None
        card = access_grants_policy_card(row)
        return {'record': row, 'policy': card}

    def create_from_form(self, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        field_errors = access_grants_run_field_checks(payload)
        if field_errors:
            return None, field_errors
        return engine.create(payload)

    def update_from_form(self, record_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        merged = deepcopy(current)
        merged.update(payload)
        field_errors = access_grants_run_field_checks(merged)
        if field_errors:
            return None, field_errors
        row, errors = engine.update(record_id, payload)
        if row:
            row['_diff'] = access_grants_diff(current, row)
        return row, errors

    def move_status(self, record_id: str, new_status: str) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        errors = access_grants_gate_transition(str(current.get('status') or ''), new_status)
        if errors:
            return None, errors
        return engine.transition(record_id, new_status)

    def export_maps(self) -> list[dict[str, str]]:
        return [access_grants_export_map(row) for row in engine.list_records()]

    def seed_if_empty(self, count: int = 10) -> int:
        return engine.seed_demo(count)


service = AccessGrantsService()


def access_grants_safe_payload(form: dict[str, Any]) -> dict[str, Any]:
    allowed = {name for name in ['principal', 'role_key', 'scope', 'justification', 'starts_on', 'ends_on', 'status']}
    clean = {}
    for name, value in form.items():
        if name in allowed or name in {'id', 'status'}:
            clean[name] = value
    return clean


def access_grants_can_delete(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status == 'requested':
        return True
    return int(row.get('health_score') or 0) < 20


def access_grants_next_statuses(current: str) -> list[str]:
    if current not in ['requested', 'approved', 'active', 'expired', 'revoked']:
        return list(['requested', 'approved', 'active', 'expired', 'revoked'])
    index = ['requested', 'approved', 'active', 'expired', 'revoked'].index(current)
    options = [current]
    if index + 1 < len(['requested', 'approved', 'active', 'expired', 'revoked']):
        options.append(['requested', 'approved', 'active', 'expired', 'revoked'][index + 1])
    if index > 0:
        options.append(['requested', 'approved', 'active', 'expired', 'revoked'][index - 1])
    unique = []
    for item in options:
        if item not in unique:
            unique.append(item)
    return unique


def access_grants_operator_actions(row: dict[str, Any]) -> list[dict[str, str]]:
    actions = [{'code': 'edit', 'label': 'Edit record'}]
    for status in access_grants_next_statuses(str(row.get('status') or '')):
        actions.append({'code': 'status:' + status, 'label': 'Move to ' + status})
    if access_grants_can_delete(row):
        actions.append({'code': 'delete', 'label': 'Remove record'})
    return actions


def access_grants_toast(action: str, ok: bool) -> str:
    if ok:
        return f'Access Grants {action} completed.'
    return f'Access Grants {action} was blocked by policy.'


def access_grants_dashboard_chip(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'key': 'access_grants',
        'title': 'Access Grants',
        'count': len(rows),
        'hot': len([row for row in rows if int(row.get('health_score') or 0) < 45]),
    }

def access_grants_form_help_principal() -> str:
    return 'Enter Principal for Access Grants. Local validation runs on save.'


def access_grants_form_help_role_key() -> str:
    return 'Enter Role Key for Access Grants. Local validation runs on save.'


def access_grants_form_help_scope() -> str:
    return 'Enter Scope for Access Grants. Local validation runs on save.'


def access_grants_form_help_justification() -> str:
    return 'Enter Justification for Access Grants. Local validation runs on save.'


def access_grants_form_help_starts_on() -> str:
    return 'Enter Starts On for Access Grants. Local validation runs on save.'


def access_grants_form_help_ends_on() -> str:
    return 'Enter Ends On for Access Grants. Local validation runs on save.'


def access_grants_form_help_status() -> str:
    return 'Enter Status for Access Grants. Local validation runs on save.'


FORM_HELP_ACCESS_GRANTS = {
    'principal': access_grants_form_help_principal(),
    'role_key': access_grants_form_help_role_key(),
    'scope': access_grants_form_help_scope(),
    'justification': access_grants_form_help_justification(),
    'starts_on': access_grants_form_help_starts_on(),
    'ends_on': access_grants_form_help_ends_on(),
    'status': access_grants_form_help_status(),
}


def access_grants_form_help() -> dict[str, str]:
    return dict(FORM_HELP_ACCESS_GRANTS)

