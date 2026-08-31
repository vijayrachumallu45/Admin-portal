"""Application service for Release Trains writes and operator actions."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.domains.release_trains.engine import engine
from app.domains.release_trains.policies import release_trains_gate_transition, release_trains_policy_card, release_trains_run_field_checks
from app.domains.release_trains.queries import release_trains_diff, release_trains_export_map
from app.domains.release_trains.reports import build_release_trains_reporter


class ReleaseTrainsService:
    """Coordinates validation, policy, persistence, and briefings for Release Trains."""

    def list_view(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        rows = engine.list_records(filters)
        reporter = build_release_trains_reporter(rows)
        return {
            'rows': rows,
            'kpis': engine.kpi_pack(),
            'pack': reporter.pack(),
        }

    def detail_view(self, record_id: str) -> dict[str, Any] | None:
        row = engine.get(record_id)
        if row is None:
            return None
        card = release_trains_policy_card(row)
        return {'record': row, 'policy': card}

    def create_from_form(self, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        field_errors = release_trains_run_field_checks(payload)
        if field_errors:
            return None, field_errors
        return engine.create(payload)

    def update_from_form(self, record_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        merged = deepcopy(current)
        merged.update(payload)
        field_errors = release_trains_run_field_checks(merged)
        if field_errors:
            return None, field_errors
        row, errors = engine.update(record_id, payload)
        if row:
            row['_diff'] = release_trains_diff(current, row)
        return row, errors

    def move_status(self, record_id: str, new_status: str) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        errors = release_trains_gate_transition(str(current.get('status') or ''), new_status)
        if errors:
            return None, errors
        return engine.transition(record_id, new_status)

    def export_maps(self) -> list[dict[str, str]]:
        return [release_trains_export_map(row) for row in engine.list_records()]

    def seed_if_empty(self, count: int = 10) -> int:
        return engine.seed_demo(count)


service = ReleaseTrainsService()


def release_trains_safe_payload(form: dict[str, Any]) -> dict[str, Any]:
    allowed = {name for name in ['version', 'codename', 'freeze_on', 'ship_on', 'status']}
    clean = {}
    for name, value in form.items():
        if name in allowed or name in {'id', 'status'}:
            clean[name] = value
    return clean


def release_trains_can_delete(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status == 'planning':
        return True
    return int(row.get('health_score') or 0) < 20


def release_trains_next_statuses(current: str) -> list[str]:
    if current not in ['planning', 'freeze', 'shipped', 'hotfix']:
        return list(['planning', 'freeze', 'shipped', 'hotfix'])
    index = ['planning', 'freeze', 'shipped', 'hotfix'].index(current)
    options = [current]
    if index + 1 < len(['planning', 'freeze', 'shipped', 'hotfix']):
        options.append(['planning', 'freeze', 'shipped', 'hotfix'][index + 1])
    if index > 0:
        options.append(['planning', 'freeze', 'shipped', 'hotfix'][index - 1])
    unique = []
    for item in options:
        if item not in unique:
            unique.append(item)
    return unique


def release_trains_operator_actions(row: dict[str, Any]) -> list[dict[str, str]]:
    actions = [{'code': 'edit', 'label': 'Edit record'}]
    for status in release_trains_next_statuses(str(row.get('status') or '')):
        actions.append({'code': 'status:' + status, 'label': 'Move to ' + status})
    if release_trains_can_delete(row):
        actions.append({'code': 'delete', 'label': 'Remove record'})
    return actions


def release_trains_toast(action: str, ok: bool) -> str:
    if ok:
        return f'Release Trains {action} completed.'
    return f'Release Trains {action} was blocked by policy.'


def release_trains_dashboard_chip(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'key': 'release_trains',
        'title': 'Release Trains',
        'count': len(rows),
        'hot': len([row for row in rows if int(row.get('health_score') or 0) < 45]),
    }

def release_trains_form_help_version() -> str:
    return 'Enter Version for Release Trains. Local validation runs on save.'


def release_trains_form_help_codename() -> str:
    return 'Enter Codename for Release Trains. Local validation runs on save.'


def release_trains_form_help_freeze_on() -> str:
    return 'Enter Freeze On for Release Trains. Local validation runs on save.'


def release_trains_form_help_ship_on() -> str:
    return 'Enter Ship On for Release Trains. Local validation runs on save.'


def release_trains_form_help_status() -> str:
    return 'Enter Status for Release Trains. Local validation runs on save.'


FORM_HELP_RELEASE_TRAINS = {
    'version': release_trains_form_help_version(),
    'codename': release_trains_form_help_codename(),
    'freeze_on': release_trains_form_help_freeze_on(),
    'ship_on': release_trains_form_help_ship_on(),
    'status': release_trains_form_help_status(),
}


def release_trains_form_help() -> dict[str, str]:
    return dict(FORM_HELP_RELEASE_TRAINS)

