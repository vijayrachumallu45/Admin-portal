"""Application service for Pulse Surveys writes and operator actions."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.domains.surveys.engine import engine
from app.domains.surveys.policies import surveys_gate_transition, surveys_policy_card, surveys_run_field_checks
from app.domains.surveys.queries import surveys_diff, surveys_export_map
from app.domains.surveys.reports import build_surveys_reporter


class SurveysService:
    """Coordinates validation, policy, persistence, and briefings for Pulse Surveys."""

    def list_view(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        rows = engine.list_records(filters)
        reporter = build_surveys_reporter(rows)
        return {
            'rows': rows,
            'kpis': engine.kpi_pack(),
            'pack': reporter.pack(),
        }

    def detail_view(self, record_id: str) -> dict[str, Any] | None:
        row = engine.get(record_id)
        if row is None:
            return None
        card = surveys_policy_card(row)
        return {'record': row, 'policy': card}

    def create_from_form(self, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        field_errors = surveys_run_field_checks(payload)
        if field_errors:
            return None, field_errors
        return engine.create(payload)

    def update_from_form(self, record_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        merged = deepcopy(current)
        merged.update(payload)
        field_errors = surveys_run_field_checks(merged)
        if field_errors:
            return None, field_errors
        row, errors = engine.update(record_id, payload)
        if row:
            row['_diff'] = surveys_diff(current, row)
        return row, errors

    def move_status(self, record_id: str, new_status: str) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        errors = surveys_gate_transition(str(current.get('status') or ''), new_status)
        if errors:
            return None, errors
        return engine.transition(record_id, new_status)

    def export_maps(self) -> list[dict[str, str]]:
        return [surveys_export_map(row) for row in engine.list_records()]

    def seed_if_empty(self, count: int = 10) -> int:
        return engine.seed_demo(count)


service = SurveysService()


def surveys_safe_payload(form: dict[str, Any]) -> dict[str, Any]:
    allowed = {name for name in ['survey_code', 'audience', 'opens_on', 'closes_on', 'target_n', 'status']}
    clean = {}
    for name, value in form.items():
        if name in allowed or name in {'id', 'status'}:
            clean[name] = value
    return clean


def surveys_can_delete(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status == 'draft':
        return True
    return int(row.get('health_score') or 0) < 20


def surveys_next_statuses(current: str) -> list[str]:
    if current not in ['draft', 'open', 'closed', 'reported']:
        return list(['draft', 'open', 'closed', 'reported'])
    index = ['draft', 'open', 'closed', 'reported'].index(current)
    options = [current]
    if index + 1 < len(['draft', 'open', 'closed', 'reported']):
        options.append(['draft', 'open', 'closed', 'reported'][index + 1])
    if index > 0:
        options.append(['draft', 'open', 'closed', 'reported'][index - 1])
    unique = []
    for item in options:
        if item not in unique:
            unique.append(item)
    return unique


def surveys_operator_actions(row: dict[str, Any]) -> list[dict[str, str]]:
    actions = [{'code': 'edit', 'label': 'Edit record'}]
    for status in surveys_next_statuses(str(row.get('status') or '')):
        actions.append({'code': 'status:' + status, 'label': 'Move to ' + status})
    if surveys_can_delete(row):
        actions.append({'code': 'delete', 'label': 'Remove record'})
    return actions


def surveys_toast(action: str, ok: bool) -> str:
    if ok:
        return f'Pulse Surveys {action} completed.'
    return f'Pulse Surveys {action} was blocked by policy.'


def surveys_dashboard_chip(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'key': 'surveys',
        'title': 'Pulse Surveys',
        'count': len(rows),
        'hot': len([row for row in rows if int(row.get('health_score') or 0) < 45]),
    }

def surveys_form_help_survey_code() -> str:
    return 'Enter Survey Code for Pulse Surveys. Local validation runs on save.'


def surveys_form_help_audience() -> str:
    return 'Enter Audience for Pulse Surveys. Local validation runs on save.'


def surveys_form_help_opens_on() -> str:
    return 'Enter Opens On for Pulse Surveys. Local validation runs on save.'


def surveys_form_help_closes_on() -> str:
    return 'Enter Closes On for Pulse Surveys. Local validation runs on save.'


def surveys_form_help_target_n() -> str:
    return 'Enter Target N for Pulse Surveys. Local validation runs on save.'


def surveys_form_help_status() -> str:
    return 'Enter Status for Pulse Surveys. Local validation runs on save.'


FORM_HELP_SURVEYS = {
    'survey_code': surveys_form_help_survey_code(),
    'audience': surveys_form_help_audience(),
    'opens_on': surveys_form_help_opens_on(),
    'closes_on': surveys_form_help_closes_on(),
    'target_n': surveys_form_help_target_n(),
    'status': surveys_form_help_status(),
}


def surveys_form_help() -> dict[str, str]:
    return dict(FORM_HELP_SURVEYS)

