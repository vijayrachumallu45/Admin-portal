"""Application service for Travel Bookings writes and operator actions."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.domains.travel_bookings.engine import engine
from app.domains.travel_bookings.policies import travel_bookings_gate_transition, travel_bookings_policy_card, travel_bookings_run_field_checks
from app.domains.travel_bookings.queries import travel_bookings_diff, travel_bookings_export_map
from app.domains.travel_bookings.reports import build_travel_bookings_reporter


class TravelBookingsService:
    """Coordinates validation, policy, persistence, and briefings for Travel Bookings."""

    def list_view(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        rows = engine.list_records(filters)
        reporter = build_travel_bookings_reporter(rows)
        return {
            'rows': rows,
            'kpis': engine.kpi_pack(),
            'pack': reporter.pack(),
        }

    def detail_view(self, record_id: str) -> dict[str, Any] | None:
        row = engine.get(record_id)
        if row is None:
            return None
        card = travel_bookings_policy_card(row)
        return {'record': row, 'policy': card}

    def create_from_form(self, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        field_errors = travel_bookings_run_field_checks(payload)
        if field_errors:
            return None, field_errors
        return engine.create(payload)

    def update_from_form(self, record_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        merged = deepcopy(current)
        merged.update(payload)
        field_errors = travel_bookings_run_field_checks(merged)
        if field_errors:
            return None, field_errors
        row, errors = engine.update(record_id, payload)
        if row:
            row['_diff'] = travel_bookings_diff(current, row)
        return row, errors

    def move_status(self, record_id: str, new_status: str) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        errors = travel_bookings_gate_transition(str(current.get('status') or ''), new_status)
        if errors:
            return None, errors
        return engine.transition(record_id, new_status)

    def export_maps(self) -> list[dict[str, str]]:
        return [travel_bookings_export_map(row) for row in engine.list_records()]

    def seed_if_empty(self, count: int = 10) -> int:
        return engine.seed_demo(count)


service = TravelBookingsService()


def travel_bookings_safe_payload(form: dict[str, Any]) -> dict[str, Any]:
    allowed = {name for name in ['booking_no', 'traveler', 'origin', 'destination', 'departs_on', 'status']}
    clean = {}
    for name, value in form.items():
        if name in allowed or name in {'id', 'status'}:
            clean[name] = value
    return clean


def travel_bookings_can_delete(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status == 'held':
        return True
    return int(row.get('health_score') or 0) < 20


def travel_bookings_next_statuses(current: str) -> list[str]:
    if current not in ['held', 'ticketed', 'in_trip', 'complete', 'void']:
        return list(['held', 'ticketed', 'in_trip', 'complete', 'void'])
    index = ['held', 'ticketed', 'in_trip', 'complete', 'void'].index(current)
    options = [current]
    if index + 1 < len(['held', 'ticketed', 'in_trip', 'complete', 'void']):
        options.append(['held', 'ticketed', 'in_trip', 'complete', 'void'][index + 1])
    if index > 0:
        options.append(['held', 'ticketed', 'in_trip', 'complete', 'void'][index - 1])
    unique = []
    for item in options:
        if item not in unique:
            unique.append(item)
    return unique


def travel_bookings_operator_actions(row: dict[str, Any]) -> list[dict[str, str]]:
    actions = [{'code': 'edit', 'label': 'Edit record'}]
    for status in travel_bookings_next_statuses(str(row.get('status') or '')):
        actions.append({'code': 'status:' + status, 'label': 'Move to ' + status})
    if travel_bookings_can_delete(row):
        actions.append({'code': 'delete', 'label': 'Remove record'})
    return actions


def travel_bookings_toast(action: str, ok: bool) -> str:
    if ok:
        return f'Travel Bookings {action} completed.'
    return f'Travel Bookings {action} was blocked by policy.'


def travel_bookings_dashboard_chip(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'key': 'travel_bookings',
        'title': 'Travel Bookings',
        'count': len(rows),
        'hot': len([row for row in rows if int(row.get('health_score') or 0) < 45]),
    }

def travel_bookings_form_help_booking_no() -> str:
    return 'Enter Booking No for Travel Bookings. Local validation runs on save.'


def travel_bookings_form_help_traveler() -> str:
    return 'Enter Traveler for Travel Bookings. Local validation runs on save.'


def travel_bookings_form_help_origin() -> str:
    return 'Enter Origin for Travel Bookings. Local validation runs on save.'


def travel_bookings_form_help_destination() -> str:
    return 'Enter Destination for Travel Bookings. Local validation runs on save.'


def travel_bookings_form_help_departs_on() -> str:
    return 'Enter Departs On for Travel Bookings. Local validation runs on save.'


def travel_bookings_form_help_status() -> str:
    return 'Enter Status for Travel Bookings. Local validation runs on save.'


FORM_HELP_TRAVEL_BOOKINGS = {
    'booking_no': travel_bookings_form_help_booking_no(),
    'traveler': travel_bookings_form_help_traveler(),
    'origin': travel_bookings_form_help_origin(),
    'destination': travel_bookings_form_help_destination(),
    'departs_on': travel_bookings_form_help_departs_on(),
    'status': travel_bookings_form_help_status(),
}


def travel_bookings_form_help() -> dict[str, str]:
    return dict(FORM_HELP_TRAVEL_BOOKINGS)

