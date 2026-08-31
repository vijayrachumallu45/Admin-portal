"""Application service for Benefits Plans writes and operator actions."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.domains.benefits_plans.engine import engine
from app.domains.benefits_plans.policies import benefits_plans_gate_transition, benefits_plans_policy_card, benefits_plans_run_field_checks
from app.domains.benefits_plans.queries import benefits_plans_diff, benefits_plans_export_map
from app.domains.benefits_plans.reports import build_benefits_plans_reporter


class BenefitsPlansService:
    """Coordinates validation, policy, persistence, and briefings for Benefits Plans."""

    def list_view(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        rows = engine.list_records(filters)
        reporter = build_benefits_plans_reporter(rows)
        return {
            'rows': rows,
            'kpis': engine.kpi_pack(),
            'pack': reporter.pack(),
        }

    def detail_view(self, record_id: str) -> dict[str, Any] | None:
        row = engine.get(record_id)
        if row is None:
            return None
        card = benefits_plans_policy_card(row)
        return {'record': row, 'policy': card}

    def create_from_form(self, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        field_errors = benefits_plans_run_field_checks(payload)
        if field_errors:
            return None, field_errors
        return engine.create(payload)

    def update_from_form(self, record_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        merged = deepcopy(current)
        merged.update(payload)
        field_errors = benefits_plans_run_field_checks(merged)
        if field_errors:
            return None, field_errors
        row, errors = engine.update(record_id, payload)
        if row:
            row['_diff'] = benefits_plans_diff(current, row)
        return row, errors

    def move_status(self, record_id: str, new_status: str) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        errors = benefits_plans_gate_transition(str(current.get('status') or ''), new_status)
        if errors:
            return None, errors
        return engine.transition(record_id, new_status)

    def export_maps(self) -> list[dict[str, str]]:
        return [benefits_plans_export_map(row) for row in engine.list_records()]

    def seed_if_empty(self, count: int = 10) -> int:
        return engine.seed_demo(count)


service = BenefitsPlansService()


def benefits_plans_safe_payload(form: dict[str, Any]) -> dict[str, Any]:
    allowed = {name for name in ['plan_code', 'plan_name', 'eligibility', 'opens_on', 'status']}
    clean = {}
    for name, value in form.items():
        if name in allowed or name in {'id', 'status'}:
            clean[name] = value
    return clean


def benefits_plans_can_delete(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status == 'draft':
        return True
    return int(row.get('health_score') or 0) < 20


def benefits_plans_next_statuses(current: str) -> list[str]:
    if current not in ['draft', 'open', 'closed']:
        return list(['draft', 'open', 'closed'])
    index = ['draft', 'open', 'closed'].index(current)
    options = [current]
    if index + 1 < len(['draft', 'open', 'closed']):
        options.append(['draft', 'open', 'closed'][index + 1])
    if index > 0:
        options.append(['draft', 'open', 'closed'][index - 1])
    unique = []
    for item in options:
        if item not in unique:
            unique.append(item)
    return unique


def benefits_plans_operator_actions(row: dict[str, Any]) -> list[dict[str, str]]:
    actions = [{'code': 'edit', 'label': 'Edit record'}]
    for status in benefits_plans_next_statuses(str(row.get('status') or '')):
        actions.append({'code': 'status:' + status, 'label': 'Move to ' + status})
    if benefits_plans_can_delete(row):
        actions.append({'code': 'delete', 'label': 'Remove record'})
    return actions


def benefits_plans_toast(action: str, ok: bool) -> str:
    if ok:
        return f'Benefits Plans {action} completed.'
    return f'Benefits Plans {action} was blocked by policy.'


def benefits_plans_dashboard_chip(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'key': 'benefits_plans',
        'title': 'Benefits Plans',
        'count': len(rows),
        'hot': len([row for row in rows if int(row.get('health_score') or 0) < 45]),
    }

def benefits_plans_form_help_plan_code() -> str:
    return 'Enter Plan Code for Benefits Plans. Local validation runs on save.'


def benefits_plans_form_help_plan_name() -> str:
    return 'Enter Plan Name for Benefits Plans. Local validation runs on save.'


def benefits_plans_form_help_eligibility() -> str:
    return 'Enter Eligibility for Benefits Plans. Local validation runs on save.'


def benefits_plans_form_help_opens_on() -> str:
    return 'Enter Opens On for Benefits Plans. Local validation runs on save.'


def benefits_plans_form_help_status() -> str:
    return 'Enter Status for Benefits Plans. Local validation runs on save.'


FORM_HELP_BENEFITS_PLANS = {
    'plan_code': benefits_plans_form_help_plan_code(),
    'plan_name': benefits_plans_form_help_plan_name(),
    'eligibility': benefits_plans_form_help_eligibility(),
    'opens_on': benefits_plans_form_help_opens_on(),
    'status': benefits_plans_form_help_status(),
}


def benefits_plans_form_help() -> dict[str, str]:
    return dict(FORM_HELP_BENEFITS_PLANS)

