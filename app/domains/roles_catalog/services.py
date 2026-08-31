"""Application service for Role Catalog writes and operator actions."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.domains.roles_catalog.engine import engine
from app.domains.roles_catalog.policies import roles_catalog_gate_transition, roles_catalog_policy_card, roles_catalog_run_field_checks
from app.domains.roles_catalog.queries import roles_catalog_diff, roles_catalog_export_map
from app.domains.roles_catalog.reports import build_roles_catalog_reporter


class RolesCatalogService:
    """Coordinates validation, policy, persistence, and briefings for Role Catalog."""

    def list_view(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        rows = engine.list_records(filters)
        reporter = build_roles_catalog_reporter(rows)
        return {
            'rows': rows,
            'kpis': engine.kpi_pack(),
            'pack': reporter.pack(),
        }

    def detail_view(self, record_id: str) -> dict[str, Any] | None:
        row = engine.get(record_id)
        if row is None:
            return None
        card = roles_catalog_policy_card(row)
        return {'record': row, 'policy': card}

    def create_from_form(self, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        field_errors = roles_catalog_run_field_checks(payload)
        if field_errors:
            return None, field_errors
        return engine.create(payload)

    def update_from_form(self, record_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        merged = deepcopy(current)
        merged.update(payload)
        field_errors = roles_catalog_run_field_checks(merged)
        if field_errors:
            return None, field_errors
        row, errors = engine.update(record_id, payload)
        if row:
            row['_diff'] = roles_catalog_diff(current, row)
        return row, errors

    def move_status(self, record_id: str, new_status: str) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        errors = roles_catalog_gate_transition(str(current.get('status') or ''), new_status)
        if errors:
            return None, errors
        return engine.transition(record_id, new_status)

    def export_maps(self) -> list[dict[str, str]]:
        return [roles_catalog_export_map(row) for row in engine.list_records()]

    def seed_if_empty(self, count: int = 10) -> int:
        return engine.seed_demo(count)


service = RolesCatalogService()


def roles_catalog_safe_payload(form: dict[str, Any]) -> dict[str, Any]:
    allowed = {name for name in ['role_key', 'display_name', 'risk_level', 'owner_team', 'max_holders', 'review_days', 'status']}
    clean = {}
    for name, value in form.items():
        if name in allowed or name in {'id', 'status'}:
            clean[name] = value
    return clean


def roles_catalog_can_delete(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status == 'draft':
        return True
    return int(row.get('health_score') or 0) < 20


def roles_catalog_next_statuses(current: str) -> list[str]:
    if current not in ['draft', 'published', 'deprecated']:
        return list(['draft', 'published', 'deprecated'])
    index = ['draft', 'published', 'deprecated'].index(current)
    options = [current]
    if index + 1 < len(['draft', 'published', 'deprecated']):
        options.append(['draft', 'published', 'deprecated'][index + 1])
    if index > 0:
        options.append(['draft', 'published', 'deprecated'][index - 1])
    unique = []
    for item in options:
        if item not in unique:
            unique.append(item)
    return unique


def roles_catalog_operator_actions(row: dict[str, Any]) -> list[dict[str, str]]:
    actions = [{'code': 'edit', 'label': 'Edit record'}]
    for status in roles_catalog_next_statuses(str(row.get('status') or '')):
        actions.append({'code': 'status:' + status, 'label': 'Move to ' + status})
    if roles_catalog_can_delete(row):
        actions.append({'code': 'delete', 'label': 'Remove record'})
    return actions


def roles_catalog_toast(action: str, ok: bool) -> str:
    if ok:
        return f'Role Catalog {action} completed.'
    return f'Role Catalog {action} was blocked by policy.'


def roles_catalog_dashboard_chip(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'key': 'roles_catalog',
        'title': 'Role Catalog',
        'count': len(rows),
        'hot': len([row for row in rows if int(row.get('health_score') or 0) < 45]),
    }

def roles_catalog_form_help_role_key() -> str:
    return 'Enter Role Key for Role Catalog. Local validation runs on save.'


def roles_catalog_form_help_display_name() -> str:
    return 'Enter Display Name for Role Catalog. Local validation runs on save.'


def roles_catalog_form_help_risk_level() -> str:
    return 'Enter Risk Level for Role Catalog. Local validation runs on save.'


def roles_catalog_form_help_owner_team() -> str:
    return 'Enter Owner Team for Role Catalog. Local validation runs on save.'


def roles_catalog_form_help_max_holders() -> str:
    return 'Enter Max Holders for Role Catalog. Local validation runs on save.'


def roles_catalog_form_help_review_days() -> str:
    return 'Enter Review Days for Role Catalog. Local validation runs on save.'


def roles_catalog_form_help_status() -> str:
    return 'Enter Status for Role Catalog. Local validation runs on save.'


FORM_HELP_ROLES_CATALOG = {
    'role_key': roles_catalog_form_help_role_key(),
    'display_name': roles_catalog_form_help_display_name(),
    'risk_level': roles_catalog_form_help_risk_level(),
    'owner_team': roles_catalog_form_help_owner_team(),
    'max_holders': roles_catalog_form_help_max_holders(),
    'review_days': roles_catalog_form_help_review_days(),
    'status': roles_catalog_form_help_status(),
}


def roles_catalog_form_help() -> dict[str, str]:
    return dict(FORM_HELP_ROLES_CATALOG)

