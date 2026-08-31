"""Application service for On-call Rotations writes and operator actions."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.domains.oncall_rotations.engine import engine
from app.domains.oncall_rotations.policies import oncall_rotations_gate_transition, oncall_rotations_policy_card, oncall_rotations_run_field_checks
from app.domains.oncall_rotations.queries import oncall_rotations_diff, oncall_rotations_export_map
from app.domains.oncall_rotations.reports import build_oncall_rotations_reporter


class OncallRotationsService:
    """Coordinates validation, policy, persistence, and briefings for On-call Rotations."""

    def list_view(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        rows = engine.list_records(filters)
        reporter = build_oncall_rotations_reporter(rows)
        return {
            'rows': rows,
            'kpis': engine.kpi_pack(),
            'pack': reporter.pack(),
        }

    def detail_view(self, record_id: str) -> dict[str, Any] | None:
        row = engine.get(record_id)
        if row is None:
            return None
        card = oncall_rotations_policy_card(row)
        return {'record': row, 'policy': card}

    def create_from_form(self, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        field_errors = oncall_rotations_run_field_checks(payload)
        if field_errors:
            return None, field_errors
        return engine.create(payload)

    def update_from_form(self, record_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        merged = deepcopy(current)
        merged.update(payload)
        field_errors = oncall_rotations_run_field_checks(merged)
        if field_errors:
            return None, field_errors
        row, errors = engine.update(record_id, payload)
        if row:
            row['_diff'] = oncall_rotations_diff(current, row)
        return row, errors

    def move_status(self, record_id: str, new_status: str) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        errors = oncall_rotations_gate_transition(str(current.get('status') or ''), new_status)
        if errors:
            return None, errors
        return engine.transition(record_id, new_status)

    def export_maps(self) -> list[dict[str, str]]:
        return [oncall_rotations_export_map(row) for row in engine.list_records()]

    def seed_if_empty(self, count: int = 10) -> int:
        return engine.seed_demo(count)


service = OncallRotationsService()


def oncall_rotations_safe_payload(form: dict[str, Any]) -> dict[str, Any]:
    allowed = {name for name in ['rotation', 'primary_name', 'backup_name', 'starts_on', 'status']}
    clean = {}
    for name, value in form.items():
        if name in allowed or name in {'id', 'status'}:
            clean[name] = value
    return clean


def oncall_rotations_can_delete(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status == 'scheduled':
        return True
    return int(row.get('health_score') or 0) < 20


def oncall_rotations_next_statuses(current: str) -> list[str]:
    if current not in ['scheduled', 'active', 'complete']:
        return list(['scheduled', 'active', 'complete'])
    index = ['scheduled', 'active', 'complete'].index(current)
    options = [current]
    if index + 1 < len(['scheduled', 'active', 'complete']):
        options.append(['scheduled', 'active', 'complete'][index + 1])
    if index > 0:
        options.append(['scheduled', 'active', 'complete'][index - 1])
    unique = []
    for item in options:
        if item not in unique:
            unique.append(item)
    return unique


def oncall_rotations_operator_actions(row: dict[str, Any]) -> list[dict[str, str]]:
    actions = [{'code': 'edit', 'label': 'Edit record'}]
    for status in oncall_rotations_next_statuses(str(row.get('status') or '')):
        actions.append({'code': 'status:' + status, 'label': 'Move to ' + status})
    if oncall_rotations_can_delete(row):
        actions.append({'code': 'delete', 'label': 'Remove record'})
    return actions


def oncall_rotations_toast(action: str, ok: bool) -> str:
    if ok:
        return f'On-call Rotations {action} completed.'
    return f'On-call Rotations {action} was blocked by policy.'


def oncall_rotations_dashboard_chip(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'key': 'oncall_rotations',
        'title': 'On-call Rotations',
        'count': len(rows),
        'hot': len([row for row in rows if int(row.get('health_score') or 0) < 45]),
    }

def oncall_rotations_form_help_rotation() -> str:
    return 'Enter Rotation for On-call Rotations. Local validation runs on save.'


def oncall_rotations_form_help_primary_name() -> str:
    return 'Enter Primary Name for On-call Rotations. Local validation runs on save.'


def oncall_rotations_form_help_backup_name() -> str:
    return 'Enter Backup Name for On-call Rotations. Local validation runs on save.'


def oncall_rotations_form_help_starts_on() -> str:
    return 'Enter Starts On for On-call Rotations. Local validation runs on save.'


def oncall_rotations_form_help_status() -> str:
    return 'Enter Status for On-call Rotations. Local validation runs on save.'


FORM_HELP_ONCALL_ROTATIONS = {
    'rotation': oncall_rotations_form_help_rotation(),
    'primary_name': oncall_rotations_form_help_primary_name(),
    'backup_name': oncall_rotations_form_help_backup_name(),
    'starts_on': oncall_rotations_form_help_starts_on(),
    'status': oncall_rotations_form_help_status(),
}


def oncall_rotations_form_help() -> dict[str, str]:
    return dict(FORM_HELP_ONCALL_ROTATIONS)

