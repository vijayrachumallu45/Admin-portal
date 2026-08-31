"""Application service for OKR Board writes and operator actions."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.domains.okrs.engine import engine
from app.domains.okrs.policies import okrs_gate_transition, okrs_policy_card, okrs_run_field_checks
from app.domains.okrs.queries import okrs_diff, okrs_export_map
from app.domains.okrs.reports import build_okrs_reporter


class OkrsService:
    """Coordinates validation, policy, persistence, and briefings for OKR Board."""

    def list_view(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        rows = engine.list_records(filters)
        reporter = build_okrs_reporter(rows)
        return {
            'rows': rows,
            'kpis': engine.kpi_pack(),
            'pack': reporter.pack(),
        }

    def detail_view(self, record_id: str) -> dict[str, Any] | None:
        row = engine.get(record_id)
        if row is None:
            return None
        card = okrs_policy_card(row)
        return {'record': row, 'policy': card}

    def create_from_form(self, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        field_errors = okrs_run_field_checks(payload)
        if field_errors:
            return None, field_errors
        return engine.create(payload)

    def update_from_form(self, record_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        merged = deepcopy(current)
        merged.update(payload)
        field_errors = okrs_run_field_checks(merged)
        if field_errors:
            return None, field_errors
        row, errors = engine.update(record_id, payload)
        if row:
            row['_diff'] = okrs_diff(current, row)
        return row, errors

    def move_status(self, record_id: str, new_status: str) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        errors = okrs_gate_transition(str(current.get('status') or ''), new_status)
        if errors:
            return None, errors
        return engine.transition(record_id, new_status)

    def export_maps(self) -> list[dict[str, str]]:
        return [okrs_export_map(row) for row in engine.list_records()]

    def seed_if_empty(self, count: int = 10) -> int:
        return engine.seed_demo(count)


service = OkrsService()


def okrs_safe_payload(form: dict[str, Any]) -> dict[str, Any]:
    allowed = {name for name in ['okr_key', 'objective', 'owner', 'confidence', 'status']}
    clean = {}
    for name, value in form.items():
        if name in allowed or name in {'id', 'status'}:
            clean[name] = value
    return clean


def okrs_can_delete(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status == 'draft':
        return True
    return int(row.get('health_score') or 0) < 20


def okrs_next_statuses(current: str) -> list[str]:
    if current not in ['draft', 'active', 'missed', 'hit']:
        return list(['draft', 'active', 'missed', 'hit'])
    index = ['draft', 'active', 'missed', 'hit'].index(current)
    options = [current]
    if index + 1 < len(['draft', 'active', 'missed', 'hit']):
        options.append(['draft', 'active', 'missed', 'hit'][index + 1])
    if index > 0:
        options.append(['draft', 'active', 'missed', 'hit'][index - 1])
    unique = []
    for item in options:
        if item not in unique:
            unique.append(item)
    return unique


def okrs_operator_actions(row: dict[str, Any]) -> list[dict[str, str]]:
    actions = [{'code': 'edit', 'label': 'Edit record'}]
    for status in okrs_next_statuses(str(row.get('status') or '')):
        actions.append({'code': 'status:' + status, 'label': 'Move to ' + status})
    if okrs_can_delete(row):
        actions.append({'code': 'delete', 'label': 'Remove record'})
    return actions


def okrs_toast(action: str, ok: bool) -> str:
    if ok:
        return f'OKR Board {action} completed.'
    return f'OKR Board {action} was blocked by policy.'


def okrs_dashboard_chip(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'key': 'okrs',
        'title': 'OKR Board',
        'count': len(rows),
        'hot': len([row for row in rows if int(row.get('health_score') or 0) < 45]),
    }

def okrs_form_help_okr_key() -> str:
    return 'Enter Okr Key for OKR Board. Local validation runs on save.'


def okrs_form_help_objective() -> str:
    return 'Enter Objective for OKR Board. Local validation runs on save.'


def okrs_form_help_owner() -> str:
    return 'Enter Owner for OKR Board. Local validation runs on save.'


def okrs_form_help_confidence() -> str:
    return 'Enter Confidence for OKR Board. Local validation runs on save.'


def okrs_form_help_status() -> str:
    return 'Enter Status for OKR Board. Local validation runs on save.'


FORM_HELP_OKRS = {
    'okr_key': okrs_form_help_okr_key(),
    'objective': okrs_form_help_objective(),
    'owner': okrs_form_help_owner(),
    'confidence': okrs_form_help_confidence(),
    'status': okrs_form_help_status(),
}


def okrs_form_help() -> dict[str, str]:
    return dict(FORM_HELP_OKRS)

