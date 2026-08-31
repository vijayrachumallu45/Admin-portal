"""Application service for Contractor Bench writes and operator actions."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.domains.contractors.engine import engine
from app.domains.contractors.policies import contractors_gate_transition, contractors_policy_card, contractors_run_field_checks
from app.domains.contractors.queries import contractors_diff, contractors_export_map
from app.domains.contractors.reports import build_contractors_reporter


class ContractorsService:
    """Coordinates validation, policy, persistence, and briefings for Contractor Bench."""

    def list_view(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        rows = engine.list_records(filters)
        reporter = build_contractors_reporter(rows)
        return {
            'rows': rows,
            'kpis': engine.kpi_pack(),
            'pack': reporter.pack(),
        }

    def detail_view(self, record_id: str) -> dict[str, Any] | None:
        row = engine.get(record_id)
        if row is None:
            return None
        card = contractors_policy_card(row)
        return {'record': row, 'policy': card}

    def create_from_form(self, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        field_errors = contractors_run_field_checks(payload)
        if field_errors:
            return None, field_errors
        return engine.create(payload)

    def update_from_form(self, record_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        merged = deepcopy(current)
        merged.update(payload)
        field_errors = contractors_run_field_checks(merged)
        if field_errors:
            return None, field_errors
        row, errors = engine.update(record_id, payload)
        if row:
            row['_diff'] = contractors_diff(current, row)
        return row, errors

    def move_status(self, record_id: str, new_status: str) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        errors = contractors_gate_transition(str(current.get('status') or ''), new_status)
        if errors:
            return None, errors
        return engine.transition(record_id, new_status)

    def export_maps(self) -> list[dict[str, str]]:
        return [contractors_export_map(row) for row in engine.list_records()]

    def seed_if_empty(self, count: int = 10) -> int:
        return engine.seed_demo(count)


service = ContractorsService()


def contractors_safe_payload(form: dict[str, Any]) -> dict[str, Any]:
    allowed = {name for name in ['contractor_no', 'full_name', 'sponsor', 'ends_on', 'status']}
    clean = {}
    for name, value in form.items():
        if name in allowed or name in {'id', 'status'}:
            clean[name] = value
    return clean


def contractors_can_delete(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status == 'active':
        return True
    return int(row.get('health_score') or 0) < 20


def contractors_next_statuses(current: str) -> list[str]:
    if current not in ['active', 'ending', 'ended']:
        return list(['active', 'ending', 'ended'])
    index = ['active', 'ending', 'ended'].index(current)
    options = [current]
    if index + 1 < len(['active', 'ending', 'ended']):
        options.append(['active', 'ending', 'ended'][index + 1])
    if index > 0:
        options.append(['active', 'ending', 'ended'][index - 1])
    unique = []
    for item in options:
        if item not in unique:
            unique.append(item)
    return unique


def contractors_operator_actions(row: dict[str, Any]) -> list[dict[str, str]]:
    actions = [{'code': 'edit', 'label': 'Edit record'}]
    for status in contractors_next_statuses(str(row.get('status') or '')):
        actions.append({'code': 'status:' + status, 'label': 'Move to ' + status})
    if contractors_can_delete(row):
        actions.append({'code': 'delete', 'label': 'Remove record'})
    return actions


def contractors_toast(action: str, ok: bool) -> str:
    if ok:
        return f'Contractor Bench {action} completed.'
    return f'Contractor Bench {action} was blocked by policy.'


def contractors_dashboard_chip(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'key': 'contractors',
        'title': 'Contractor Bench',
        'count': len(rows),
        'hot': len([row for row in rows if int(row.get('health_score') or 0) < 45]),
    }

def contractors_form_help_contractor_no() -> str:
    return 'Enter Contractor No for Contractor Bench. Local validation runs on save.'


def contractors_form_help_full_name() -> str:
    return 'Enter Full Name for Contractor Bench. Local validation runs on save.'


def contractors_form_help_sponsor() -> str:
    return 'Enter Sponsor for Contractor Bench. Local validation runs on save.'


def contractors_form_help_ends_on() -> str:
    return 'Enter Ends On for Contractor Bench. Local validation runs on save.'


def contractors_form_help_status() -> str:
    return 'Enter Status for Contractor Bench. Local validation runs on save.'


FORM_HELP_CONTRACTORS = {
    'contractor_no': contractors_form_help_contractor_no(),
    'full_name': contractors_form_help_full_name(),
    'sponsor': contractors_form_help_sponsor(),
    'ends_on': contractors_form_help_ends_on(),
    'status': contractors_form_help_status(),
}


def contractors_form_help() -> dict[str, str]:
    return dict(FORM_HELP_CONTRACTORS)

