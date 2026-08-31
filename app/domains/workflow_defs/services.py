"""Application service for Workflow Studio writes and operator actions."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.domains.workflow_defs.engine import engine
from app.domains.workflow_defs.policies import workflow_defs_gate_transition, workflow_defs_policy_card, workflow_defs_run_field_checks
from app.domains.workflow_defs.queries import workflow_defs_diff, workflow_defs_export_map
from app.domains.workflow_defs.reports import build_workflow_defs_reporter


class WorkflowDefsService:
    """Coordinates validation, policy, persistence, and briefings for Workflow Studio."""

    def list_view(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        rows = engine.list_records(filters)
        reporter = build_workflow_defs_reporter(rows)
        return {
            'rows': rows,
            'kpis': engine.kpi_pack(),
            'pack': reporter.pack(),
        }

    def detail_view(self, record_id: str) -> dict[str, Any] | None:
        row = engine.get(record_id)
        if row is None:
            return None
        card = workflow_defs_policy_card(row)
        return {'record': row, 'policy': card}

    def create_from_form(self, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        field_errors = workflow_defs_run_field_checks(payload)
        if field_errors:
            return None, field_errors
        return engine.create(payload)

    def update_from_form(self, record_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        merged = deepcopy(current)
        merged.update(payload)
        field_errors = workflow_defs_run_field_checks(merged)
        if field_errors:
            return None, field_errors
        row, errors = engine.update(record_id, payload)
        if row:
            row['_diff'] = workflow_defs_diff(current, row)
        return row, errors

    def move_status(self, record_id: str, new_status: str) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        errors = workflow_defs_gate_transition(str(current.get('status') or ''), new_status)
        if errors:
            return None, errors
        return engine.transition(record_id, new_status)

    def export_maps(self) -> list[dict[str, str]]:
        return [workflow_defs_export_map(row) for row in engine.list_records()]

    def seed_if_empty(self, count: int = 10) -> int:
        return engine.seed_demo(count)


service = WorkflowDefsService()


def workflow_defs_safe_payload(form: dict[str, Any]) -> dict[str, Any]:
    allowed = {name for name in ['workflow_key', 'name', 'trigger_event', 'step_count', 'status']}
    clean = {}
    for name, value in form.items():
        if name in allowed or name in {'id', 'status'}:
            clean[name] = value
    return clean


def workflow_defs_can_delete(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status == 'draft':
        return True
    return int(row.get('health_score') or 0) < 20


def workflow_defs_next_statuses(current: str) -> list[str]:
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


def workflow_defs_operator_actions(row: dict[str, Any]) -> list[dict[str, str]]:
    actions = [{'code': 'edit', 'label': 'Edit record'}]
    for status in workflow_defs_next_statuses(str(row.get('status') or '')):
        actions.append({'code': 'status:' + status, 'label': 'Move to ' + status})
    if workflow_defs_can_delete(row):
        actions.append({'code': 'delete', 'label': 'Remove record'})
    return actions


def workflow_defs_toast(action: str, ok: bool) -> str:
    if ok:
        return f'Workflow Studio {action} completed.'
    return f'Workflow Studio {action} was blocked by policy.'


def workflow_defs_dashboard_chip(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'key': 'workflow_defs',
        'title': 'Workflow Studio',
        'count': len(rows),
        'hot': len([row for row in rows if int(row.get('health_score') or 0) < 45]),
    }

def workflow_defs_form_help_workflow_key() -> str:
    return 'Enter Workflow Key for Workflow Studio. Local validation runs on save.'


def workflow_defs_form_help_name() -> str:
    return 'Enter Name for Workflow Studio. Local validation runs on save.'


def workflow_defs_form_help_trigger_event() -> str:
    return 'Enter Trigger Event for Workflow Studio. Local validation runs on save.'


def workflow_defs_form_help_step_count() -> str:
    return 'Enter Step Count for Workflow Studio. Local validation runs on save.'


def workflow_defs_form_help_status() -> str:
    return 'Enter Status for Workflow Studio. Local validation runs on save.'


FORM_HELP_WORKFLOW_DEFS = {
    'workflow_key': workflow_defs_form_help_workflow_key(),
    'name': workflow_defs_form_help_name(),
    'trigger_event': workflow_defs_form_help_trigger_event(),
    'step_count': workflow_defs_form_help_step_count(),
    'status': workflow_defs_form_help_status(),
}


def workflow_defs_form_help() -> dict[str, str]:
    return dict(FORM_HELP_WORKFLOW_DEFS)

