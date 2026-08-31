"""Application service for Revenue Forecast writes and operator actions."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.domains.forecasts.engine import engine
from app.domains.forecasts.policies import forecasts_gate_transition, forecasts_policy_card, forecasts_run_field_checks
from app.domains.forecasts.queries import forecasts_diff, forecasts_export_map
from app.domains.forecasts.reports import build_forecasts_reporter


class ForecastsService:
    """Coordinates validation, policy, persistence, and briefings for Revenue Forecast."""

    def list_view(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        rows = engine.list_records(filters)
        reporter = build_forecasts_reporter(rows)
        return {
            'rows': rows,
            'kpis': engine.kpi_pack(),
            'pack': reporter.pack(),
        }

    def detail_view(self, record_id: str) -> dict[str, Any] | None:
        row = engine.get(record_id)
        if row is None:
            return None
        card = forecasts_policy_card(row)
        return {'record': row, 'policy': card}

    def create_from_form(self, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        field_errors = forecasts_run_field_checks(payload)
        if field_errors:
            return None, field_errors
        return engine.create(payload)

    def update_from_form(self, record_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        merged = deepcopy(current)
        merged.update(payload)
        field_errors = forecasts_run_field_checks(merged)
        if field_errors:
            return None, field_errors
        row, errors = engine.update(record_id, payload)
        if row:
            row['_diff'] = forecasts_diff(current, row)
        return row, errors

    def move_status(self, record_id: str, new_status: str) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        errors = forecasts_gate_transition(str(current.get('status') or ''), new_status)
        if errors:
            return None, errors
        return engine.transition(record_id, new_status)

    def export_maps(self) -> list[dict[str, str]]:
        return [forecasts_export_map(row) for row in engine.list_records()]

    def seed_if_empty(self, count: int = 10) -> int:
        return engine.seed_demo(count)


service = ForecastsService()


def forecasts_safe_payload(form: dict[str, Any]) -> dict[str, Any]:
    allowed = {name for name in ['period', 'commit_cents', 'best_cents', 'pipeline_cents', 'owner', 'status']}
    clean = {}
    for name, value in form.items():
        if name in allowed or name in {'id', 'status'}:
            clean[name] = value
    return clean


def forecasts_can_delete(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status == 'working':
        return True
    return int(row.get('health_score') or 0) < 20


def forecasts_next_statuses(current: str) -> list[str]:
    if current not in ['working', 'locked', 'actualized']:
        return list(['working', 'locked', 'actualized'])
    index = ['working', 'locked', 'actualized'].index(current)
    options = [current]
    if index + 1 < len(['working', 'locked', 'actualized']):
        options.append(['working', 'locked', 'actualized'][index + 1])
    if index > 0:
        options.append(['working', 'locked', 'actualized'][index - 1])
    unique = []
    for item in options:
        if item not in unique:
            unique.append(item)
    return unique


def forecasts_operator_actions(row: dict[str, Any]) -> list[dict[str, str]]:
    actions = [{'code': 'edit', 'label': 'Edit record'}]
    for status in forecasts_next_statuses(str(row.get('status') or '')):
        actions.append({'code': 'status:' + status, 'label': 'Move to ' + status})
    if forecasts_can_delete(row):
        actions.append({'code': 'delete', 'label': 'Remove record'})
    return actions


def forecasts_toast(action: str, ok: bool) -> str:
    if ok:
        return f'Revenue Forecast {action} completed.'
    return f'Revenue Forecast {action} was blocked by policy.'


def forecasts_dashboard_chip(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'key': 'forecasts',
        'title': 'Revenue Forecast',
        'count': len(rows),
        'hot': len([row for row in rows if int(row.get('health_score') or 0) < 45]),
    }

def forecasts_form_help_period() -> str:
    return 'Enter Period for Revenue Forecast. Local validation runs on save.'


def forecasts_form_help_commit_cents() -> str:
    return 'Enter Commit Cents for Revenue Forecast. Local validation runs on save.'


def forecasts_form_help_best_cents() -> str:
    return 'Enter Best Cents for Revenue Forecast. Local validation runs on save.'


def forecasts_form_help_pipeline_cents() -> str:
    return 'Enter Pipeline Cents for Revenue Forecast. Local validation runs on save.'


def forecasts_form_help_owner() -> str:
    return 'Enter Owner for Revenue Forecast. Local validation runs on save.'


def forecasts_form_help_status() -> str:
    return 'Enter Status for Revenue Forecast. Local validation runs on save.'


FORM_HELP_FORECASTS = {
    'period': forecasts_form_help_period(),
    'commit_cents': forecasts_form_help_commit_cents(),
    'best_cents': forecasts_form_help_best_cents(),
    'pipeline_cents': forecasts_form_help_pipeline_cents(),
    'owner': forecasts_form_help_owner(),
    'status': forecasts_form_help_status(),
}


def forecasts_form_help() -> dict[str, str]:
    return dict(FORM_HELP_FORECASTS)

