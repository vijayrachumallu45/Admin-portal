"""Application service for Facilities writes and operator actions."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.domains.facilities.engine import engine
from app.domains.facilities.policies import facilities_gate_transition, facilities_policy_card, facilities_run_field_checks
from app.domains.facilities.queries import facilities_diff, facilities_export_map
from app.domains.facilities.reports import build_facilities_reporter


class FacilitiesService:
    """Coordinates validation, policy, persistence, and briefings for Facilities."""

    def list_view(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        rows = engine.list_records(filters)
        reporter = build_facilities_reporter(rows)
        return {
            'rows': rows,
            'kpis': engine.kpi_pack(),
            'pack': reporter.pack(),
        }

    def detail_view(self, record_id: str) -> dict[str, Any] | None:
        row = engine.get(record_id)
        if row is None:
            return None
        card = facilities_policy_card(row)
        return {'record': row, 'policy': card}

    def create_from_form(self, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        field_errors = facilities_run_field_checks(payload)
        if field_errors:
            return None, field_errors
        return engine.create(payload)

    def update_from_form(self, record_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        merged = deepcopy(current)
        merged.update(payload)
        field_errors = facilities_run_field_checks(merged)
        if field_errors:
            return None, field_errors
        row, errors = engine.update(record_id, payload)
        if row:
            row['_diff'] = facilities_diff(current, row)
        return row, errors

    def move_status(self, record_id: str, new_status: str) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        errors = facilities_gate_transition(str(current.get('status') or ''), new_status)
        if errors:
            return None, errors
        return engine.transition(record_id, new_status)

    def export_maps(self) -> list[dict[str, str]]:
        return [facilities_export_map(row) for row in engine.list_records()]

    def seed_if_empty(self, count: int = 10) -> int:
        return engine.seed_demo(count)


service = FacilitiesService()


def facilities_safe_payload(form: dict[str, Any]) -> dict[str, Any]:
    allowed = {name for name in ['site_code', 'address', 'capacity', 'safety_owner', 'status']}
    clean = {}
    for name, value in form.items():
        if name in allowed or name in {'id', 'status'}:
            clean[name] = value
    return clean


def facilities_can_delete(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status == 'open':
        return True
    return int(row.get('health_score') or 0) < 20


def facilities_next_statuses(current: str) -> list[str]:
    if current not in ['open', 'limited', 'closed']:
        return list(['open', 'limited', 'closed'])
    index = ['open', 'limited', 'closed'].index(current)
    options = [current]
    if index + 1 < len(['open', 'limited', 'closed']):
        options.append(['open', 'limited', 'closed'][index + 1])
    if index > 0:
        options.append(['open', 'limited', 'closed'][index - 1])
    unique = []
    for item in options:
        if item not in unique:
            unique.append(item)
    return unique


def facilities_operator_actions(row: dict[str, Any]) -> list[dict[str, str]]:
    actions = [{'code': 'edit', 'label': 'Edit record'}]
    for status in facilities_next_statuses(str(row.get('status') or '')):
        actions.append({'code': 'status:' + status, 'label': 'Move to ' + status})
    if facilities_can_delete(row):
        actions.append({'code': 'delete', 'label': 'Remove record'})
    return actions


def facilities_toast(action: str, ok: bool) -> str:
    if ok:
        return f'Facilities {action} completed.'
    return f'Facilities {action} was blocked by policy.'


def facilities_dashboard_chip(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'key': 'facilities',
        'title': 'Facilities',
        'count': len(rows),
        'hot': len([row for row in rows if int(row.get('health_score') or 0) < 45]),
    }

def facilities_form_help_site_code() -> str:
    return 'Enter Site Code for Facilities. Local validation runs on save.'


def facilities_form_help_address() -> str:
    return 'Enter Address for Facilities. Local validation runs on save.'


def facilities_form_help_capacity() -> str:
    return 'Enter Capacity for Facilities. Local validation runs on save.'


def facilities_form_help_safety_owner() -> str:
    return 'Enter Safety Owner for Facilities. Local validation runs on save.'


def facilities_form_help_status() -> str:
    return 'Enter Status for Facilities. Local validation runs on save.'


FORM_HELP_FACILITIES = {
    'site_code': facilities_form_help_site_code(),
    'address': facilities_form_help_address(),
    'capacity': facilities_form_help_capacity(),
    'safety_owner': facilities_form_help_safety_owner(),
    'status': facilities_form_help_status(),
}


def facilities_form_help() -> dict[str, str]:
    return dict(FORM_HELP_FACILITIES)

