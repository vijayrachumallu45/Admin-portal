"""Application service for SLA Policies writes and operator actions."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.domains.sla_policies.engine import engine
from app.domains.sla_policies.policies import sla_policies_gate_transition, sla_policies_policy_card, sla_policies_run_field_checks
from app.domains.sla_policies.queries import sla_policies_diff, sla_policies_export_map
from app.domains.sla_policies.reports import build_sla_policies_reporter


class SlaPoliciesService:
    """Coordinates validation, policy, persistence, and briefings for SLA Policies."""

    def list_view(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        rows = engine.list_records(filters)
        reporter = build_sla_policies_reporter(rows)
        return {
            'rows': rows,
            'kpis': engine.kpi_pack(),
            'pack': reporter.pack(),
        }

    def detail_view(self, record_id: str) -> dict[str, Any] | None:
        row = engine.get(record_id)
        if row is None:
            return None
        card = sla_policies_policy_card(row)
        return {'record': row, 'policy': card}

    def create_from_form(self, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        field_errors = sla_policies_run_field_checks(payload)
        if field_errors:
            return None, field_errors
        return engine.create(payload)

    def update_from_form(self, record_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        merged = deepcopy(current)
        merged.update(payload)
        field_errors = sla_policies_run_field_checks(merged)
        if field_errors:
            return None, field_errors
        row, errors = engine.update(record_id, payload)
        if row:
            row['_diff'] = sla_policies_diff(current, row)
        return row, errors

    def move_status(self, record_id: str, new_status: str) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        errors = sla_policies_gate_transition(str(current.get('status') or ''), new_status)
        if errors:
            return None, errors
        return engine.transition(record_id, new_status)

    def export_maps(self) -> list[dict[str, str]]:
        return [sla_policies_export_map(row) for row in engine.list_records()]

    def seed_if_empty(self, count: int = 10) -> int:
        return engine.seed_demo(count)


service = SlaPoliciesService()


def sla_policies_safe_payload(form: dict[str, Any]) -> dict[str, Any]:
    allowed = {name for name in ['policy_code', 'severity', 'respond_minutes', 'restore_minutes', 'status']}
    clean = {}
    for name, value in form.items():
        if name in allowed or name in {'id', 'status'}:
            clean[name] = value
    return clean


def sla_policies_can_delete(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status == 'draft':
        return True
    return int(row.get('health_score') or 0) < 20


def sla_policies_next_statuses(current: str) -> list[str]:
    if current not in ['draft', 'live', 'paused']:
        return list(['draft', 'live', 'paused'])
    index = ['draft', 'live', 'paused'].index(current)
    options = [current]
    if index + 1 < len(['draft', 'live', 'paused']):
        options.append(['draft', 'live', 'paused'][index + 1])
    if index > 0:
        options.append(['draft', 'live', 'paused'][index - 1])
    unique = []
    for item in options:
        if item not in unique:
            unique.append(item)
    return unique


def sla_policies_operator_actions(row: dict[str, Any]) -> list[dict[str, str]]:
    actions = [{'code': 'edit', 'label': 'Edit record'}]
    for status in sla_policies_next_statuses(str(row.get('status') or '')):
        actions.append({'code': 'status:' + status, 'label': 'Move to ' + status})
    if sla_policies_can_delete(row):
        actions.append({'code': 'delete', 'label': 'Remove record'})
    return actions


def sla_policies_toast(action: str, ok: bool) -> str:
    if ok:
        return f'SLA Policies {action} completed.'
    return f'SLA Policies {action} was blocked by policy.'


def sla_policies_dashboard_chip(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'key': 'sla_policies',
        'title': 'SLA Policies',
        'count': len(rows),
        'hot': len([row for row in rows if int(row.get('health_score') or 0) < 45]),
    }

def sla_policies_form_help_policy_code() -> str:
    return 'Enter Policy Code for SLA Policies. Local validation runs on save.'


def sla_policies_form_help_severity() -> str:
    return 'Enter Severity for SLA Policies. Local validation runs on save.'


def sla_policies_form_help_respond_minutes() -> str:
    return 'Enter Respond Minutes for SLA Policies. Local validation runs on save.'


def sla_policies_form_help_restore_minutes() -> str:
    return 'Enter Restore Minutes for SLA Policies. Local validation runs on save.'


def sla_policies_form_help_status() -> str:
    return 'Enter Status for SLA Policies. Local validation runs on save.'


FORM_HELP_SLA_POLICIES = {
    'policy_code': sla_policies_form_help_policy_code(),
    'severity': sla_policies_form_help_severity(),
    'respond_minutes': sla_policies_form_help_respond_minutes(),
    'restore_minutes': sla_policies_form_help_restore_minutes(),
    'status': sla_policies_form_help_status(),
}


def sla_policies_form_help() -> dict[str, str]:
    return dict(FORM_HELP_SLA_POLICIES)

