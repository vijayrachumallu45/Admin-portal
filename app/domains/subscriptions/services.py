"""Application service for Subscription Book writes and operator actions."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.domains.subscriptions.engine import engine
from app.domains.subscriptions.policies import subscriptions_gate_transition, subscriptions_policy_card, subscriptions_run_field_checks
from app.domains.subscriptions.queries import subscriptions_diff, subscriptions_export_map
from app.domains.subscriptions.reports import build_subscriptions_reporter


class SubscriptionsService:
    """Coordinates validation, policy, persistence, and briefings for Subscription Book."""

    def list_view(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        rows = engine.list_records(filters)
        reporter = build_subscriptions_reporter(rows)
        return {
            'rows': rows,
            'kpis': engine.kpi_pack(),
            'pack': reporter.pack(),
        }

    def detail_view(self, record_id: str) -> dict[str, Any] | None:
        row = engine.get(record_id)
        if row is None:
            return None
        card = subscriptions_policy_card(row)
        return {'record': row, 'policy': card}

    def create_from_form(self, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        field_errors = subscriptions_run_field_checks(payload)
        if field_errors:
            return None, field_errors
        return engine.create(payload)

    def update_from_form(self, record_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        merged = deepcopy(current)
        merged.update(payload)
        field_errors = subscriptions_run_field_checks(merged)
        if field_errors:
            return None, field_errors
        row, errors = engine.update(record_id, payload)
        if row:
            row['_diff'] = subscriptions_diff(current, row)
        return row, errors

    def move_status(self, record_id: str, new_status: str) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        errors = subscriptions_gate_transition(str(current.get('status') or ''), new_status)
        if errors:
            return None, errors
        return engine.transition(record_id, new_status)

    def export_maps(self) -> list[dict[str, str]]:
        return [subscriptions_export_map(row) for row in engine.list_records()]

    def seed_if_empty(self, count: int = 10) -> int:
        return engine.seed_demo(count)


service = SubscriptionsService()


def subscriptions_safe_payload(form: dict[str, Any]) -> dict[str, Any]:
    allowed = {name for name in ['account', 'plan_code', 'seats', 'renew_on', 'term_months', 'arr_cents', 'status']}
    clean = {}
    for name, value in form.items():
        if name in allowed or name in {'id', 'status'}:
            clean[name] = value
    return clean


def subscriptions_can_delete(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status == 'trial':
        return True
    return int(row.get('health_score') or 0) < 20


def subscriptions_next_statuses(current: str) -> list[str]:
    if current not in ['trial', 'active', 'past_due', 'cancelled']:
        return list(['trial', 'active', 'past_due', 'cancelled'])
    index = ['trial', 'active', 'past_due', 'cancelled'].index(current)
    options = [current]
    if index + 1 < len(['trial', 'active', 'past_due', 'cancelled']):
        options.append(['trial', 'active', 'past_due', 'cancelled'][index + 1])
    if index > 0:
        options.append(['trial', 'active', 'past_due', 'cancelled'][index - 1])
    unique = []
    for item in options:
        if item not in unique:
            unique.append(item)
    return unique


def subscriptions_operator_actions(row: dict[str, Any]) -> list[dict[str, str]]:
    actions = [{'code': 'edit', 'label': 'Edit record'}]
    for status in subscriptions_next_statuses(str(row.get('status') or '')):
        actions.append({'code': 'status:' + status, 'label': 'Move to ' + status})
    if subscriptions_can_delete(row):
        actions.append({'code': 'delete', 'label': 'Remove record'})
    return actions


def subscriptions_toast(action: str, ok: bool) -> str:
    if ok:
        return f'Subscription Book {action} completed.'
    return f'Subscription Book {action} was blocked by policy.'


def subscriptions_dashboard_chip(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'key': 'subscriptions',
        'title': 'Subscription Book',
        'count': len(rows),
        'hot': len([row for row in rows if int(row.get('health_score') or 0) < 45]),
    }

def subscriptions_form_help_account() -> str:
    return 'Enter Account for Subscription Book. Local validation runs on save.'


def subscriptions_form_help_plan_code() -> str:
    return 'Enter Plan Code for Subscription Book. Local validation runs on save.'


def subscriptions_form_help_seats() -> str:
    return 'Enter Seats for Subscription Book. Local validation runs on save.'


def subscriptions_form_help_renew_on() -> str:
    return 'Enter Renew On for Subscription Book. Local validation runs on save.'


def subscriptions_form_help_term_months() -> str:
    return 'Enter Term Months for Subscription Book. Local validation runs on save.'


def subscriptions_form_help_arr_cents() -> str:
    return 'Enter Arr Cents for Subscription Book. Local validation runs on save.'


def subscriptions_form_help_status() -> str:
    return 'Enter Status for Subscription Book. Local validation runs on save.'


FORM_HELP_SUBSCRIPTIONS = {
    'account': subscriptions_form_help_account(),
    'plan_code': subscriptions_form_help_plan_code(),
    'seats': subscriptions_form_help_seats(),
    'renew_on': subscriptions_form_help_renew_on(),
    'term_months': subscriptions_form_help_term_months(),
    'arr_cents': subscriptions_form_help_arr_cents(),
    'status': subscriptions_form_help_status(),
}


def subscriptions_form_help() -> dict[str, str]:
    return dict(FORM_HELP_SUBSCRIPTIONS)

