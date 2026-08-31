"""Application service for Notification Center writes and operator actions."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.domains.notifications.engine import engine
from app.domains.notifications.policies import notifications_gate_transition, notifications_policy_card, notifications_run_field_checks
from app.domains.notifications.queries import notifications_diff, notifications_export_map
from app.domains.notifications.reports import build_notifications_reporter


class NotificationsService:
    """Coordinates validation, policy, persistence, and briefings for Notification Center."""

    def list_view(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        rows = engine.list_records(filters)
        reporter = build_notifications_reporter(rows)
        return {
            'rows': rows,
            'kpis': engine.kpi_pack(),
            'pack': reporter.pack(),
        }

    def detail_view(self, record_id: str) -> dict[str, Any] | None:
        row = engine.get(record_id)
        if row is None:
            return None
        card = notifications_policy_card(row)
        return {'record': row, 'policy': card}

    def create_from_form(self, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        field_errors = notifications_run_field_checks(payload)
        if field_errors:
            return None, field_errors
        return engine.create(payload)

    def update_from_form(self, record_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        merged = deepcopy(current)
        merged.update(payload)
        field_errors = notifications_run_field_checks(merged)
        if field_errors:
            return None, field_errors
        row, errors = engine.update(record_id, payload)
        if row:
            row['_diff'] = notifications_diff(current, row)
        return row, errors

    def move_status(self, record_id: str, new_status: str) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        errors = notifications_gate_transition(str(current.get('status') or ''), new_status)
        if errors:
            return None, errors
        return engine.transition(record_id, new_status)

    def export_maps(self) -> list[dict[str, str]]:
        return [notifications_export_map(row) for row in engine.list_records()]

    def seed_if_empty(self, count: int = 10) -> int:
        return engine.seed_demo(count)


service = NotificationsService()


def notifications_safe_payload(form: dict[str, Any]) -> dict[str, Any]:
    allowed = {name for name in ['headline', 'audience', 'priority', 'published_on', 'status']}
    clean = {}
    for name, value in form.items():
        if name in allowed or name in {'id', 'status'}:
            clean[name] = value
    return clean


def notifications_can_delete(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status == 'draft':
        return True
    return int(row.get('health_score') or 0) < 20


def notifications_next_statuses(current: str) -> list[str]:
    if current not in ['draft', 'sent', 'acked']:
        return list(['draft', 'sent', 'acked'])
    index = ['draft', 'sent', 'acked'].index(current)
    options = [current]
    if index + 1 < len(['draft', 'sent', 'acked']):
        options.append(['draft', 'sent', 'acked'][index + 1])
    if index > 0:
        options.append(['draft', 'sent', 'acked'][index - 1])
    unique = []
    for item in options:
        if item not in unique:
            unique.append(item)
    return unique


def notifications_operator_actions(row: dict[str, Any]) -> list[dict[str, str]]:
    actions = [{'code': 'edit', 'label': 'Edit record'}]
    for status in notifications_next_statuses(str(row.get('status') or '')):
        actions.append({'code': 'status:' + status, 'label': 'Move to ' + status})
    if notifications_can_delete(row):
        actions.append({'code': 'delete', 'label': 'Remove record'})
    return actions


def notifications_toast(action: str, ok: bool) -> str:
    if ok:
        return f'Notification Center {action} completed.'
    return f'Notification Center {action} was blocked by policy.'


def notifications_dashboard_chip(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'key': 'notifications',
        'title': 'Notification Center',
        'count': len(rows),
        'hot': len([row for row in rows if int(row.get('health_score') or 0) < 45]),
    }

def notifications_form_help_headline() -> str:
    return 'Enter Headline for Notification Center. Local validation runs on save.'


def notifications_form_help_audience() -> str:
    return 'Enter Audience for Notification Center. Local validation runs on save.'


def notifications_form_help_priority() -> str:
    return 'Enter Priority for Notification Center. Local validation runs on save.'


def notifications_form_help_published_on() -> str:
    return 'Enter Published On for Notification Center. Local validation runs on save.'


def notifications_form_help_status() -> str:
    return 'Enter Status for Notification Center. Local validation runs on save.'


FORM_HELP_NOTIFICATIONS = {
    'headline': notifications_form_help_headline(),
    'audience': notifications_form_help_audience(),
    'priority': notifications_form_help_priority(),
    'published_on': notifications_form_help_published_on(),
    'status': notifications_form_help_status(),
}


def notifications_form_help() -> dict[str, str]:
    return dict(FORM_HELP_NOTIFICATIONS)

