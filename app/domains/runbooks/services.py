"""Application service for Ops Runbooks writes and operator actions."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.domains.runbooks.engine import engine
from app.domains.runbooks.policies import runbooks_gate_transition, runbooks_policy_card, runbooks_run_field_checks
from app.domains.runbooks.queries import runbooks_diff, runbooks_export_map
from app.domains.runbooks.reports import build_runbooks_reporter


class RunbooksService:
    """Coordinates validation, policy, persistence, and briefings for Ops Runbooks."""

    def list_view(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        rows = engine.list_records(filters)
        reporter = build_runbooks_reporter(rows)
        return {
            'rows': rows,
            'kpis': engine.kpi_pack(),
            'pack': reporter.pack(),
        }

    def detail_view(self, record_id: str) -> dict[str, Any] | None:
        row = engine.get(record_id)
        if row is None:
            return None
        card = runbooks_policy_card(row)
        return {'record': row, 'policy': card}

    def create_from_form(self, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        field_errors = runbooks_run_field_checks(payload)
        if field_errors:
            return None, field_errors
        return engine.create(payload)

    def update_from_form(self, record_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        merged = deepcopy(current)
        merged.update(payload)
        field_errors = runbooks_run_field_checks(merged)
        if field_errors:
            return None, field_errors
        row, errors = engine.update(record_id, payload)
        if row:
            row['_diff'] = runbooks_diff(current, row)
        return row, errors

    def move_status(self, record_id: str, new_status: str) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        errors = runbooks_gate_transition(str(current.get('status') or ''), new_status)
        if errors:
            return None, errors
        return engine.transition(record_id, new_status)

    def export_maps(self) -> list[dict[str, str]]:
        return [runbooks_export_map(row) for row in engine.list_records()]

    def seed_if_empty(self, count: int = 10) -> int:
        return engine.seed_demo(count)


service = RunbooksService()


def runbooks_safe_payload(form: dict[str, Any]) -> dict[str, Any]:
    allowed = {name for name in ['runbook_key', 'title', 'owner', 'step_count', 'status']}
    clean = {}
    for name, value in form.items():
        if name in allowed or name in {'id', 'status'}:
            clean[name] = value
    return clean


def runbooks_can_delete(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status == 'draft':
        return True
    return int(row.get('health_score') or 0) < 20


def runbooks_next_statuses(current: str) -> list[str]:
    if current not in ['draft', 'certified', 'stale']:
        return list(['draft', 'certified', 'stale'])
    index = ['draft', 'certified', 'stale'].index(current)
    options = [current]
    if index + 1 < len(['draft', 'certified', 'stale']):
        options.append(['draft', 'certified', 'stale'][index + 1])
    if index > 0:
        options.append(['draft', 'certified', 'stale'][index - 1])
    unique = []
    for item in options:
        if item not in unique:
            unique.append(item)
    return unique


def runbooks_operator_actions(row: dict[str, Any]) -> list[dict[str, str]]:
    actions = [{'code': 'edit', 'label': 'Edit record'}]
    for status in runbooks_next_statuses(str(row.get('status') or '')):
        actions.append({'code': 'status:' + status, 'label': 'Move to ' + status})
    if runbooks_can_delete(row):
        actions.append({'code': 'delete', 'label': 'Remove record'})
    return actions


def runbooks_toast(action: str, ok: bool) -> str:
    if ok:
        return f'Ops Runbooks {action} completed.'
    return f'Ops Runbooks {action} was blocked by policy.'


def runbooks_dashboard_chip(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'key': 'runbooks',
        'title': 'Ops Runbooks',
        'count': len(rows),
        'hot': len([row for row in rows if int(row.get('health_score') or 0) < 45]),
    }

def runbooks_form_help_runbook_key() -> str:
    return 'Enter Runbook Key for Ops Runbooks. Local validation runs on save.'


def runbooks_form_help_title() -> str:
    return 'Enter Title for Ops Runbooks. Local validation runs on save.'


def runbooks_form_help_owner() -> str:
    return 'Enter Owner for Ops Runbooks. Local validation runs on save.'


def runbooks_form_help_step_count() -> str:
    return 'Enter Step Count for Ops Runbooks. Local validation runs on save.'


def runbooks_form_help_status() -> str:
    return 'Enter Status for Ops Runbooks. Local validation runs on save.'


FORM_HELP_RUNBOOKS = {
    'runbook_key': runbooks_form_help_runbook_key(),
    'title': runbooks_form_help_title(),
    'owner': runbooks_form_help_owner(),
    'step_count': runbooks_form_help_step_count(),
    'status': runbooks_form_help_status(),
}


def runbooks_form_help() -> dict[str, str]:
    return dict(FORM_HELP_RUNBOOKS)

