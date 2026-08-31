"""Application service for NPS Responses writes and operator actions."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.domains.nps_responses.engine import engine
from app.domains.nps_responses.policies import nps_responses_gate_transition, nps_responses_policy_card, nps_responses_run_field_checks
from app.domains.nps_responses.queries import nps_responses_diff, nps_responses_export_map
from app.domains.nps_responses.reports import build_nps_responses_reporter


class NpsResponsesService:
    """Coordinates validation, policy, persistence, and briefings for NPS Responses."""

    def list_view(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        rows = engine.list_records(filters)
        reporter = build_nps_responses_reporter(rows)
        return {
            'rows': rows,
            'kpis': engine.kpi_pack(),
            'pack': reporter.pack(),
        }

    def detail_view(self, record_id: str) -> dict[str, Any] | None:
        row = engine.get(record_id)
        if row is None:
            return None
        card = nps_responses_policy_card(row)
        return {'record': row, 'policy': card}

    def create_from_form(self, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        field_errors = nps_responses_run_field_checks(payload)
        if field_errors:
            return None, field_errors
        return engine.create(payload)

    def update_from_form(self, record_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        merged = deepcopy(current)
        merged.update(payload)
        field_errors = nps_responses_run_field_checks(merged)
        if field_errors:
            return None, field_errors
        row, errors = engine.update(record_id, payload)
        if row:
            row['_diff'] = nps_responses_diff(current, row)
        return row, errors

    def move_status(self, record_id: str, new_status: str) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        errors = nps_responses_gate_transition(str(current.get('status') or ''), new_status)
        if errors:
            return None, errors
        return engine.transition(record_id, new_status)

    def export_maps(self) -> list[dict[str, str]]:
        return [nps_responses_export_map(row) for row in engine.list_records()]

    def seed_if_empty(self, count: int = 10) -> int:
        return engine.seed_demo(count)


service = NpsResponsesService()


def nps_responses_safe_payload(form: dict[str, Any]) -> dict[str, Any]:
    allowed = {name for name in ['account_name', 'score', 'comment', 'owner', 'status']}
    clean = {}
    for name, value in form.items():
        if name in allowed or name in {'id', 'status'}:
            clean[name] = value
    return clean


def nps_responses_can_delete(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status == 'new':
        return True
    return int(row.get('health_score') or 0) < 20


def nps_responses_next_statuses(current: str) -> list[str]:
    if current not in ['new', 'follow_up', 'closed']:
        return list(['new', 'follow_up', 'closed'])
    index = ['new', 'follow_up', 'closed'].index(current)
    options = [current]
    if index + 1 < len(['new', 'follow_up', 'closed']):
        options.append(['new', 'follow_up', 'closed'][index + 1])
    if index > 0:
        options.append(['new', 'follow_up', 'closed'][index - 1])
    unique = []
    for item in options:
        if item not in unique:
            unique.append(item)
    return unique


def nps_responses_operator_actions(row: dict[str, Any]) -> list[dict[str, str]]:
    actions = [{'code': 'edit', 'label': 'Edit record'}]
    for status in nps_responses_next_statuses(str(row.get('status') or '')):
        actions.append({'code': 'status:' + status, 'label': 'Move to ' + status})
    if nps_responses_can_delete(row):
        actions.append({'code': 'delete', 'label': 'Remove record'})
    return actions


def nps_responses_toast(action: str, ok: bool) -> str:
    if ok:
        return f'NPS Responses {action} completed.'
    return f'NPS Responses {action} was blocked by policy.'


def nps_responses_dashboard_chip(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'key': 'nps_responses',
        'title': 'NPS Responses',
        'count': len(rows),
        'hot': len([row for row in rows if int(row.get('health_score') or 0) < 45]),
    }

def nps_responses_form_help_account_name() -> str:
    return 'Enter Account Name for NPS Responses. Local validation runs on save.'


def nps_responses_form_help_score() -> str:
    return 'Enter Score for NPS Responses. Local validation runs on save.'


def nps_responses_form_help_comment() -> str:
    return 'Enter Comment for NPS Responses. Local validation runs on save.'


def nps_responses_form_help_owner() -> str:
    return 'Enter Owner for NPS Responses. Local validation runs on save.'


def nps_responses_form_help_status() -> str:
    return 'Enter Status for NPS Responses. Local validation runs on save.'


FORM_HELP_NPS_RESPONSES = {
    'account_name': nps_responses_form_help_account_name(),
    'score': nps_responses_form_help_score(),
    'comment': nps_responses_form_help_comment(),
    'owner': nps_responses_form_help_owner(),
    'status': nps_responses_form_help_status(),
}


def nps_responses_form_help() -> dict[str, str]:
    return dict(FORM_HELP_NPS_RESPONSES)

