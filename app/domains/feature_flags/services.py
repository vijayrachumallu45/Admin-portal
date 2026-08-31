"""Application service for Feature Flags writes and operator actions."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.domains.feature_flags.engine import engine
from app.domains.feature_flags.policies import feature_flags_gate_transition, feature_flags_policy_card, feature_flags_run_field_checks
from app.domains.feature_flags.queries import feature_flags_diff, feature_flags_export_map
from app.domains.feature_flags.reports import build_feature_flags_reporter


class FeatureFlagsService:
    """Coordinates validation, policy, persistence, and briefings for Feature Flags."""

    def list_view(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        rows = engine.list_records(filters)
        reporter = build_feature_flags_reporter(rows)
        return {
            'rows': rows,
            'kpis': engine.kpi_pack(),
            'pack': reporter.pack(),
        }

    def detail_view(self, record_id: str) -> dict[str, Any] | None:
        row = engine.get(record_id)
        if row is None:
            return None
        card = feature_flags_policy_card(row)
        return {'record': row, 'policy': card}

    def create_from_form(self, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        field_errors = feature_flags_run_field_checks(payload)
        if field_errors:
            return None, field_errors
        return engine.create(payload)

    def update_from_form(self, record_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        merged = deepcopy(current)
        merged.update(payload)
        field_errors = feature_flags_run_field_checks(merged)
        if field_errors:
            return None, field_errors
        row, errors = engine.update(record_id, payload)
        if row:
            row['_diff'] = feature_flags_diff(current, row)
        return row, errors

    def move_status(self, record_id: str, new_status: str) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        errors = feature_flags_gate_transition(str(current.get('status') or ''), new_status)
        if errors:
            return None, errors
        return engine.transition(record_id, new_status)

    def export_maps(self) -> list[dict[str, str]]:
        return [feature_flags_export_map(row) for row in engine.list_records()]

    def seed_if_empty(self, count: int = 10) -> int:
        return engine.seed_demo(count)


service = FeatureFlagsService()


def feature_flags_safe_payload(form: dict[str, Any]) -> dict[str, Any]:
    allowed = {name for name in ['flag_key', 'description', 'percent', 'owner', 'status']}
    clean = {}
    for name, value in form.items():
        if name in allowed or name in {'id', 'status'}:
            clean[name] = value
    return clean


def feature_flags_can_delete(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status == 'off':
        return True
    return int(row.get('health_score') or 0) < 20


def feature_flags_next_statuses(current: str) -> list[str]:
    if current not in ['off', 'ramp', 'on', 'retired']:
        return list(['off', 'ramp', 'on', 'retired'])
    index = ['off', 'ramp', 'on', 'retired'].index(current)
    options = [current]
    if index + 1 < len(['off', 'ramp', 'on', 'retired']):
        options.append(['off', 'ramp', 'on', 'retired'][index + 1])
    if index > 0:
        options.append(['off', 'ramp', 'on', 'retired'][index - 1])
    unique = []
    for item in options:
        if item not in unique:
            unique.append(item)
    return unique


def feature_flags_operator_actions(row: dict[str, Any]) -> list[dict[str, str]]:
    actions = [{'code': 'edit', 'label': 'Edit record'}]
    for status in feature_flags_next_statuses(str(row.get('status') or '')):
        actions.append({'code': 'status:' + status, 'label': 'Move to ' + status})
    if feature_flags_can_delete(row):
        actions.append({'code': 'delete', 'label': 'Remove record'})
    return actions


def feature_flags_toast(action: str, ok: bool) -> str:
    if ok:
        return f'Feature Flags {action} completed.'
    return f'Feature Flags {action} was blocked by policy.'


def feature_flags_dashboard_chip(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'key': 'feature_flags',
        'title': 'Feature Flags',
        'count': len(rows),
        'hot': len([row for row in rows if int(row.get('health_score') or 0) < 45]),
    }

def feature_flags_form_help_flag_key() -> str:
    return 'Enter Flag Key for Feature Flags. Local validation runs on save.'


def feature_flags_form_help_description() -> str:
    return 'Enter Description for Feature Flags. Local validation runs on save.'


def feature_flags_form_help_percent() -> str:
    return 'Enter Percent for Feature Flags. Local validation runs on save.'


def feature_flags_form_help_owner() -> str:
    return 'Enter Owner for Feature Flags. Local validation runs on save.'


def feature_flags_form_help_status() -> str:
    return 'Enter Status for Feature Flags. Local validation runs on save.'


FORM_HELP_FEATURE_FLAGS = {
    'flag_key': feature_flags_form_help_flag_key(),
    'description': feature_flags_form_help_description(),
    'percent': feature_flags_form_help_percent(),
    'owner': feature_flags_form_help_owner(),
    'status': feature_flags_form_help_status(),
}


def feature_flags_form_help() -> dict[str, str]:
    return dict(FORM_HELP_FEATURE_FLAGS)

