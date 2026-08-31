"""Application service for Board Packs writes and operator actions."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.domains.board_packs.engine import engine
from app.domains.board_packs.policies import board_packs_gate_transition, board_packs_policy_card, board_packs_run_field_checks
from app.domains.board_packs.queries import board_packs_diff, board_packs_export_map
from app.domains.board_packs.reports import build_board_packs_reporter


class BoardPacksService:
    """Coordinates validation, policy, persistence, and briefings for Board Packs."""

    def list_view(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        rows = engine.list_records(filters)
        reporter = build_board_packs_reporter(rows)
        return {
            'rows': rows,
            'kpis': engine.kpi_pack(),
            'pack': reporter.pack(),
        }

    def detail_view(self, record_id: str) -> dict[str, Any] | None:
        row = engine.get(record_id)
        if row is None:
            return None
        card = board_packs_policy_card(row)
        return {'record': row, 'policy': card}

    def create_from_form(self, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        field_errors = board_packs_run_field_checks(payload)
        if field_errors:
            return None, field_errors
        return engine.create(payload)

    def update_from_form(self, record_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        merged = deepcopy(current)
        merged.update(payload)
        field_errors = board_packs_run_field_checks(merged)
        if field_errors:
            return None, field_errors
        row, errors = engine.update(record_id, payload)
        if row:
            row['_diff'] = board_packs_diff(current, row)
        return row, errors

    def move_status(self, record_id: str, new_status: str) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        errors = board_packs_gate_transition(str(current.get('status') or ''), new_status)
        if errors:
            return None, errors
        return engine.transition(record_id, new_status)

    def export_maps(self) -> list[dict[str, str]]:
        return [board_packs_export_map(row) for row in engine.list_records()]

    def seed_if_empty(self, count: int = 10) -> int:
        return engine.seed_demo(count)


service = BoardPacksService()


def board_packs_safe_payload(form: dict[str, Any]) -> dict[str, Any]:
    allowed = {name for name in ['pack_code', 'meeting_on', 'owner', 'page_count', 'status']}
    clean = {}
    for name, value in form.items():
        if name in allowed or name in {'id', 'status'}:
            clean[name] = value
    return clean


def board_packs_can_delete(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status == 'collecting':
        return True
    return int(row.get('health_score') or 0) < 20


def board_packs_next_statuses(current: str) -> list[str]:
    if current not in ['collecting', 'frozen', 'sent']:
        return list(['collecting', 'frozen', 'sent'])
    index = ['collecting', 'frozen', 'sent'].index(current)
    options = [current]
    if index + 1 < len(['collecting', 'frozen', 'sent']):
        options.append(['collecting', 'frozen', 'sent'][index + 1])
    if index > 0:
        options.append(['collecting', 'frozen', 'sent'][index - 1])
    unique = []
    for item in options:
        if item not in unique:
            unique.append(item)
    return unique


def board_packs_operator_actions(row: dict[str, Any]) -> list[dict[str, str]]:
    actions = [{'code': 'edit', 'label': 'Edit record'}]
    for status in board_packs_next_statuses(str(row.get('status') or '')):
        actions.append({'code': 'status:' + status, 'label': 'Move to ' + status})
    if board_packs_can_delete(row):
        actions.append({'code': 'delete', 'label': 'Remove record'})
    return actions


def board_packs_toast(action: str, ok: bool) -> str:
    if ok:
        return f'Board Packs {action} completed.'
    return f'Board Packs {action} was blocked by policy.'


def board_packs_dashboard_chip(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'key': 'board_packs',
        'title': 'Board Packs',
        'count': len(rows),
        'hot': len([row for row in rows if int(row.get('health_score') or 0) < 45]),
    }

def board_packs_form_help_pack_code() -> str:
    return 'Enter Pack Code for Board Packs. Local validation runs on save.'


def board_packs_form_help_meeting_on() -> str:
    return 'Enter Meeting On for Board Packs. Local validation runs on save.'


def board_packs_form_help_owner() -> str:
    return 'Enter Owner for Board Packs. Local validation runs on save.'


def board_packs_form_help_page_count() -> str:
    return 'Enter Page Count for Board Packs. Local validation runs on save.'


def board_packs_form_help_status() -> str:
    return 'Enter Status for Board Packs. Local validation runs on save.'


FORM_HELP_BOARD_PACKS = {
    'pack_code': board_packs_form_help_pack_code(),
    'meeting_on': board_packs_form_help_meeting_on(),
    'owner': board_packs_form_help_owner(),
    'page_count': board_packs_form_help_page_count(),
    'status': board_packs_form_help_status(),
}


def board_packs_form_help() -> dict[str, str]:
    return dict(FORM_HELP_BOARD_PACKS)

