"""Application service for Partner Desk writes and operator actions."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.domains.partners.engine import engine
from app.domains.partners.policies import partners_gate_transition, partners_policy_card, partners_run_field_checks
from app.domains.partners.queries import partners_diff, partners_export_map
from app.domains.partners.reports import build_partners_reporter


class PartnersService:
    """Coordinates validation, policy, persistence, and briefings for Partner Desk."""

    def list_view(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        rows = engine.list_records(filters)
        reporter = build_partners_reporter(rows)
        return {
            'rows': rows,
            'kpis': engine.kpi_pack(),
            'pack': reporter.pack(),
        }

    def detail_view(self, record_id: str) -> dict[str, Any] | None:
        row = engine.get(record_id)
        if row is None:
            return None
        card = partners_policy_card(row)
        return {'record': row, 'policy': card}

    def create_from_form(self, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        field_errors = partners_run_field_checks(payload)
        if field_errors:
            return None, field_errors
        return engine.create(payload)

    def update_from_form(self, record_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        merged = deepcopy(current)
        merged.update(payload)
        field_errors = partners_run_field_checks(merged)
        if field_errors:
            return None, field_errors
        row, errors = engine.update(record_id, payload)
        if row:
            row['_diff'] = partners_diff(current, row)
        return row, errors

    def move_status(self, record_id: str, new_status: str) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        errors = partners_gate_transition(str(current.get('status') or ''), new_status)
        if errors:
            return None, errors
        return engine.transition(record_id, new_status)

    def export_maps(self) -> list[dict[str, str]]:
        return [partners_export_map(row) for row in engine.list_records()]

    def seed_if_empty(self, count: int = 10) -> int:
        return engine.seed_demo(count)


service = PartnersService()


def partners_safe_payload(form: dict[str, Any]) -> dict[str, Any]:
    allowed = {name for name in ['partner_code', 'name', 'tier', 'region', 'certified', 'status']}
    clean = {}
    for name, value in form.items():
        if name in allowed or name in {'id', 'status'}:
            clean[name] = value
    return clean


def partners_can_delete(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status == 'applicant':
        return True
    return int(row.get('health_score') or 0) < 20


def partners_next_statuses(current: str) -> list[str]:
    if current not in ['applicant', 'active', 'probation', 'ended']:
        return list(['applicant', 'active', 'probation', 'ended'])
    index = ['applicant', 'active', 'probation', 'ended'].index(current)
    options = [current]
    if index + 1 < len(['applicant', 'active', 'probation', 'ended']):
        options.append(['applicant', 'active', 'probation', 'ended'][index + 1])
    if index > 0:
        options.append(['applicant', 'active', 'probation', 'ended'][index - 1])
    unique = []
    for item in options:
        if item not in unique:
            unique.append(item)
    return unique


def partners_operator_actions(row: dict[str, Any]) -> list[dict[str, str]]:
    actions = [{'code': 'edit', 'label': 'Edit record'}]
    for status in partners_next_statuses(str(row.get('status') or '')):
        actions.append({'code': 'status:' + status, 'label': 'Move to ' + status})
    if partners_can_delete(row):
        actions.append({'code': 'delete', 'label': 'Remove record'})
    return actions


def partners_toast(action: str, ok: bool) -> str:
    if ok:
        return f'Partner Desk {action} completed.'
    return f'Partner Desk {action} was blocked by policy.'


def partners_dashboard_chip(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'key': 'partners',
        'title': 'Partner Desk',
        'count': len(rows),
        'hot': len([row for row in rows if int(row.get('health_score') or 0) < 45]),
    }

def partners_form_help_partner_code() -> str:
    return 'Enter Partner Code for Partner Desk. Local validation runs on save.'


def partners_form_help_name() -> str:
    return 'Enter Name for Partner Desk. Local validation runs on save.'


def partners_form_help_tier() -> str:
    return 'Enter Tier for Partner Desk. Local validation runs on save.'


def partners_form_help_region() -> str:
    return 'Enter Region for Partner Desk. Local validation runs on save.'


def partners_form_help_certified() -> str:
    return 'Enter Certified for Partner Desk. Local validation runs on save.'


def partners_form_help_status() -> str:
    return 'Enter Status for Partner Desk. Local validation runs on save.'


FORM_HELP_PARTNERS = {
    'partner_code': partners_form_help_partner_code(),
    'name': partners_form_help_name(),
    'tier': partners_form_help_tier(),
    'region': partners_form_help_region(),
    'certified': partners_form_help_certified(),
    'status': partners_form_help_status(),
}


def partners_form_help() -> dict[str, str]:
    return dict(FORM_HELP_PARTNERS)

