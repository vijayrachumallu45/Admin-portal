"""Application service for Compliance Controls writes and operator actions."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.domains.compliance_controls.engine import engine
from app.domains.compliance_controls.policies import compliance_controls_gate_transition, compliance_controls_policy_card, compliance_controls_run_field_checks
from app.domains.compliance_controls.queries import compliance_controls_diff, compliance_controls_export_map
from app.domains.compliance_controls.reports import build_compliance_controls_reporter


class ComplianceControlsService:
    """Coordinates validation, policy, persistence, and briefings for Compliance Controls."""

    def list_view(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        rows = engine.list_records(filters)
        reporter = build_compliance_controls_reporter(rows)
        return {
            'rows': rows,
            'kpis': engine.kpi_pack(),
            'pack': reporter.pack(),
        }

    def detail_view(self, record_id: str) -> dict[str, Any] | None:
        row = engine.get(record_id)
        if row is None:
            return None
        card = compliance_controls_policy_card(row)
        return {'record': row, 'policy': card}

    def create_from_form(self, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        field_errors = compliance_controls_run_field_checks(payload)
        if field_errors:
            return None, field_errors
        return engine.create(payload)

    def update_from_form(self, record_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        merged = deepcopy(current)
        merged.update(payload)
        field_errors = compliance_controls_run_field_checks(merged)
        if field_errors:
            return None, field_errors
        row, errors = engine.update(record_id, payload)
        if row:
            row['_diff'] = compliance_controls_diff(current, row)
        return row, errors

    def move_status(self, record_id: str, new_status: str) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        errors = compliance_controls_gate_transition(str(current.get('status') or ''), new_status)
        if errors:
            return None, errors
        return engine.transition(record_id, new_status)

    def export_maps(self) -> list[dict[str, str]]:
        return [compliance_controls_export_map(row) for row in engine.list_records()]

    def seed_if_empty(self, count: int = 10) -> int:
        return engine.seed_demo(count)


service = ComplianceControlsService()


def compliance_controls_safe_payload(form: dict[str, Any]) -> dict[str, Any]:
    allowed = {name for name in ['control_id', 'statement', 'framework', 'owner', 'test_days', 'status']}
    clean = {}
    for name, value in form.items():
        if name in allowed or name in {'id', 'status'}:
            clean[name] = value
    return clean


def compliance_controls_can_delete(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status == 'designed':
        return True
    return int(row.get('health_score') or 0) < 20


def compliance_controls_next_statuses(current: str) -> list[str]:
    if current not in ['designed', 'operating', 'gap', 'retired']:
        return list(['designed', 'operating', 'gap', 'retired'])
    index = ['designed', 'operating', 'gap', 'retired'].index(current)
    options = [current]
    if index + 1 < len(['designed', 'operating', 'gap', 'retired']):
        options.append(['designed', 'operating', 'gap', 'retired'][index + 1])
    if index > 0:
        options.append(['designed', 'operating', 'gap', 'retired'][index - 1])
    unique = []
    for item in options:
        if item not in unique:
            unique.append(item)
    return unique


def compliance_controls_operator_actions(row: dict[str, Any]) -> list[dict[str, str]]:
    actions = [{'code': 'edit', 'label': 'Edit record'}]
    for status in compliance_controls_next_statuses(str(row.get('status') or '')):
        actions.append({'code': 'status:' + status, 'label': 'Move to ' + status})
    if compliance_controls_can_delete(row):
        actions.append({'code': 'delete', 'label': 'Remove record'})
    return actions


def compliance_controls_toast(action: str, ok: bool) -> str:
    if ok:
        return f'Compliance Controls {action} completed.'
    return f'Compliance Controls {action} was blocked by policy.'


def compliance_controls_dashboard_chip(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'key': 'compliance_controls',
        'title': 'Compliance Controls',
        'count': len(rows),
        'hot': len([row for row in rows if int(row.get('health_score') or 0) < 45]),
    }

def compliance_controls_form_help_control_id() -> str:
    return 'Enter Control Id for Compliance Controls. Local validation runs on save.'


def compliance_controls_form_help_statement() -> str:
    return 'Enter Statement for Compliance Controls. Local validation runs on save.'


def compliance_controls_form_help_framework() -> str:
    return 'Enter Framework for Compliance Controls. Local validation runs on save.'


def compliance_controls_form_help_owner() -> str:
    return 'Enter Owner for Compliance Controls. Local validation runs on save.'


def compliance_controls_form_help_test_days() -> str:
    return 'Enter Test Days for Compliance Controls. Local validation runs on save.'


def compliance_controls_form_help_status() -> str:
    return 'Enter Status for Compliance Controls. Local validation runs on save.'


FORM_HELP_COMPLIANCE_CONTROLS = {
    'control_id': compliance_controls_form_help_control_id(),
    'statement': compliance_controls_form_help_statement(),
    'framework': compliance_controls_form_help_framework(),
    'owner': compliance_controls_form_help_owner(),
    'test_days': compliance_controls_form_help_test_days(),
    'status': compliance_controls_form_help_status(),
}


def compliance_controls_form_help() -> dict[str, str]:
    return dict(FORM_HELP_COMPLIANCE_CONTROLS)

