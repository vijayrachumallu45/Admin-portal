"""Application service for Compensation Bands writes and operator actions."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.domains.compensation_bands.engine import engine
from app.domains.compensation_bands.policies import compensation_bands_gate_transition, compensation_bands_policy_card, compensation_bands_run_field_checks
from app.domains.compensation_bands.queries import compensation_bands_diff, compensation_bands_export_map
from app.domains.compensation_bands.reports import build_compensation_bands_reporter


class CompensationBandsService:
    """Coordinates validation, policy, persistence, and briefings for Compensation Bands."""

    def list_view(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        rows = engine.list_records(filters)
        reporter = build_compensation_bands_reporter(rows)
        return {
            'rows': rows,
            'kpis': engine.kpi_pack(),
            'pack': reporter.pack(),
        }

    def detail_view(self, record_id: str) -> dict[str, Any] | None:
        row = engine.get(record_id)
        if row is None:
            return None
        card = compensation_bands_policy_card(row)
        return {'record': row, 'policy': card}

    def create_from_form(self, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        field_errors = compensation_bands_run_field_checks(payload)
        if field_errors:
            return None, field_errors
        return engine.create(payload)

    def update_from_form(self, record_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        merged = deepcopy(current)
        merged.update(payload)
        field_errors = compensation_bands_run_field_checks(merged)
        if field_errors:
            return None, field_errors
        row, errors = engine.update(record_id, payload)
        if row:
            row['_diff'] = compensation_bands_diff(current, row)
        return row, errors

    def move_status(self, record_id: str, new_status: str) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        errors = compensation_bands_gate_transition(str(current.get('status') or ''), new_status)
        if errors:
            return None, errors
        return engine.transition(record_id, new_status)

    def export_maps(self) -> list[dict[str, str]]:
        return [compensation_bands_export_map(row) for row in engine.list_records()]

    def seed_if_empty(self, count: int = 10) -> int:
        return engine.seed_demo(count)


service = CompensationBandsService()


def compensation_bands_safe_payload(form: dict[str, Any]) -> dict[str, Any]:
    allowed = {name for name in ['band_code', 'level_name', 'min_cents', 'max_cents', 'status']}
    clean = {}
    for name, value in form.items():
        if name in allowed or name in {'id', 'status'}:
            clean[name] = value
    return clean


def compensation_bands_can_delete(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status == 'draft':
        return True
    return int(row.get('health_score') or 0) < 20


def compensation_bands_next_statuses(current: str) -> list[str]:
    if current not in ['draft', 'live', 'retired']:
        return list(['draft', 'live', 'retired'])
    index = ['draft', 'live', 'retired'].index(current)
    options = [current]
    if index + 1 < len(['draft', 'live', 'retired']):
        options.append(['draft', 'live', 'retired'][index + 1])
    if index > 0:
        options.append(['draft', 'live', 'retired'][index - 1])
    unique = []
    for item in options:
        if item not in unique:
            unique.append(item)
    return unique


def compensation_bands_operator_actions(row: dict[str, Any]) -> list[dict[str, str]]:
    actions = [{'code': 'edit', 'label': 'Edit record'}]
    for status in compensation_bands_next_statuses(str(row.get('status') or '')):
        actions.append({'code': 'status:' + status, 'label': 'Move to ' + status})
    if compensation_bands_can_delete(row):
        actions.append({'code': 'delete', 'label': 'Remove record'})
    return actions


def compensation_bands_toast(action: str, ok: bool) -> str:
    if ok:
        return f'Compensation Bands {action} completed.'
    return f'Compensation Bands {action} was blocked by policy.'


def compensation_bands_dashboard_chip(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'key': 'compensation_bands',
        'title': 'Compensation Bands',
        'count': len(rows),
        'hot': len([row for row in rows if int(row.get('health_score') or 0) < 45]),
    }

def compensation_bands_form_help_band_code() -> str:
    return 'Enter Band Code for Compensation Bands. Local validation runs on save.'


def compensation_bands_form_help_level_name() -> str:
    return 'Enter Level Name for Compensation Bands. Local validation runs on save.'


def compensation_bands_form_help_min_cents() -> str:
    return 'Enter Min Cents for Compensation Bands. Local validation runs on save.'


def compensation_bands_form_help_max_cents() -> str:
    return 'Enter Max Cents for Compensation Bands. Local validation runs on save.'


def compensation_bands_form_help_status() -> str:
    return 'Enter Status for Compensation Bands. Local validation runs on save.'


FORM_HELP_COMPENSATION_BANDS = {
    'band_code': compensation_bands_form_help_band_code(),
    'level_name': compensation_bands_form_help_level_name(),
    'min_cents': compensation_bands_form_help_min_cents(),
    'max_cents': compensation_bands_form_help_max_cents(),
    'status': compensation_bands_form_help_status(),
}


def compensation_bands_form_help() -> dict[str, str]:
    return dict(FORM_HELP_COMPENSATION_BANDS)

