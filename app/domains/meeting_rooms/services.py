"""Application service for Meeting Rooms writes and operator actions."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.domains.meeting_rooms.engine import engine
from app.domains.meeting_rooms.policies import meeting_rooms_gate_transition, meeting_rooms_policy_card, meeting_rooms_run_field_checks
from app.domains.meeting_rooms.queries import meeting_rooms_diff, meeting_rooms_export_map
from app.domains.meeting_rooms.reports import build_meeting_rooms_reporter


class MeetingRoomsService:
    """Coordinates validation, policy, persistence, and briefings for Meeting Rooms."""

    def list_view(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        rows = engine.list_records(filters)
        reporter = build_meeting_rooms_reporter(rows)
        return {
            'rows': rows,
            'kpis': engine.kpi_pack(),
            'pack': reporter.pack(),
        }

    def detail_view(self, record_id: str) -> dict[str, Any] | None:
        row = engine.get(record_id)
        if row is None:
            return None
        card = meeting_rooms_policy_card(row)
        return {'record': row, 'policy': card}

    def create_from_form(self, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        field_errors = meeting_rooms_run_field_checks(payload)
        if field_errors:
            return None, field_errors
        return engine.create(payload)

    def update_from_form(self, record_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        merged = deepcopy(current)
        merged.update(payload)
        field_errors = meeting_rooms_run_field_checks(merged)
        if field_errors:
            return None, field_errors
        row, errors = engine.update(record_id, payload)
        if row:
            row['_diff'] = meeting_rooms_diff(current, row)
        return row, errors

    def move_status(self, record_id: str, new_status: str) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        errors = meeting_rooms_gate_transition(str(current.get('status') or ''), new_status)
        if errors:
            return None, errors
        return engine.transition(record_id, new_status)

    def export_maps(self) -> list[dict[str, str]]:
        return [meeting_rooms_export_map(row) for row in engine.list_records()]

    def seed_if_empty(self, count: int = 10) -> int:
        return engine.seed_demo(count)


service = MeetingRoomsService()


def meeting_rooms_safe_payload(form: dict[str, Any]) -> dict[str, Any]:
    allowed = {name for name in ['room_code', 'floor', 'capacity', 'equipment', 'status']}
    clean = {}
    for name, value in form.items():
        if name in allowed or name in {'id', 'status'}:
            clean[name] = value
    return clean


def meeting_rooms_can_delete(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status == 'open':
        return True
    return int(row.get('health_score') or 0) < 20


def meeting_rooms_next_statuses(current: str) -> list[str]:
    if current not in ['open', 'held', 'offline']:
        return list(['open', 'held', 'offline'])
    index = ['open', 'held', 'offline'].index(current)
    options = [current]
    if index + 1 < len(['open', 'held', 'offline']):
        options.append(['open', 'held', 'offline'][index + 1])
    if index > 0:
        options.append(['open', 'held', 'offline'][index - 1])
    unique = []
    for item in options:
        if item not in unique:
            unique.append(item)
    return unique


def meeting_rooms_operator_actions(row: dict[str, Any]) -> list[dict[str, str]]:
    actions = [{'code': 'edit', 'label': 'Edit record'}]
    for status in meeting_rooms_next_statuses(str(row.get('status') or '')):
        actions.append({'code': 'status:' + status, 'label': 'Move to ' + status})
    if meeting_rooms_can_delete(row):
        actions.append({'code': 'delete', 'label': 'Remove record'})
    return actions


def meeting_rooms_toast(action: str, ok: bool) -> str:
    if ok:
        return f'Meeting Rooms {action} completed.'
    return f'Meeting Rooms {action} was blocked by policy.'


def meeting_rooms_dashboard_chip(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'key': 'meeting_rooms',
        'title': 'Meeting Rooms',
        'count': len(rows),
        'hot': len([row for row in rows if int(row.get('health_score') or 0) < 45]),
    }

def meeting_rooms_form_help_room_code() -> str:
    return 'Enter Room Code for Meeting Rooms. Local validation runs on save.'


def meeting_rooms_form_help_floor() -> str:
    return 'Enter Floor for Meeting Rooms. Local validation runs on save.'


def meeting_rooms_form_help_capacity() -> str:
    return 'Enter Capacity for Meeting Rooms. Local validation runs on save.'


def meeting_rooms_form_help_equipment() -> str:
    return 'Enter Equipment for Meeting Rooms. Local validation runs on save.'


def meeting_rooms_form_help_status() -> str:
    return 'Enter Status for Meeting Rooms. Local validation runs on save.'


FORM_HELP_MEETING_ROOMS = {
    'room_code': meeting_rooms_form_help_room_code(),
    'floor': meeting_rooms_form_help_floor(),
    'capacity': meeting_rooms_form_help_capacity(),
    'equipment': meeting_rooms_form_help_equipment(),
    'status': meeting_rooms_form_help_status(),
}


def meeting_rooms_form_help() -> dict[str, str]:
    return dict(FORM_HELP_MEETING_ROOMS)

