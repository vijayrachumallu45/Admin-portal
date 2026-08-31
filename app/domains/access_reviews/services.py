"""Application service for Access Reviews writes and operator actions."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.domains.access_reviews.engine import engine
from app.domains.access_reviews.policies import access_reviews_gate_transition, access_reviews_policy_card, access_reviews_run_field_checks
from app.domains.access_reviews.queries import access_reviews_diff, access_reviews_export_map
from app.domains.access_reviews.reports import build_access_reviews_reporter


class AccessReviewsService:
    """Coordinates validation, policy, persistence, and briefings for Access Reviews."""

    def list_view(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        rows = engine.list_records(filters)
        reporter = build_access_reviews_reporter(rows)
        return {
            'rows': rows,
            'kpis': engine.kpi_pack(),
            'pack': reporter.pack(),
        }

    def detail_view(self, record_id: str) -> dict[str, Any] | None:
        row = engine.get(record_id)
        if row is None:
            return None
        card = access_reviews_policy_card(row)
        return {'record': row, 'policy': card}

    def create_from_form(self, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        field_errors = access_reviews_run_field_checks(payload)
        if field_errors:
            return None, field_errors
        return engine.create(payload)

    def update_from_form(self, record_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        merged = deepcopy(current)
        merged.update(payload)
        field_errors = access_reviews_run_field_checks(merged)
        if field_errors:
            return None, field_errors
        row, errors = engine.update(record_id, payload)
        if row:
            row['_diff'] = access_reviews_diff(current, row)
        return row, errors

    def move_status(self, record_id: str, new_status: str) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        errors = access_reviews_gate_transition(str(current.get('status') or ''), new_status)
        if errors:
            return None, errors
        return engine.transition(record_id, new_status)

    def export_maps(self) -> list[dict[str, str]]:
        return [access_reviews_export_map(row) for row in engine.list_records()]

    def seed_if_empty(self, count: int = 10) -> int:
        return engine.seed_demo(count)


service = AccessReviewsService()


def access_reviews_safe_payload(form: dict[str, Any]) -> dict[str, Any]:
    allowed = {name for name in ['campaign', 'scope', 'reviewer', 'due_on', 'item_count', 'status']}
    clean = {}
    for name, value in form.items():
        if name in allowed or name in {'id', 'status'}:
            clean[name] = value
    return clean


def access_reviews_can_delete(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status == 'scheduled':
        return True
    return int(row.get('health_score') or 0) < 20


def access_reviews_next_statuses(current: str) -> list[str]:
    if current not in ['scheduled', 'in_progress', 'complete', 'overdue']:
        return list(['scheduled', 'in_progress', 'complete', 'overdue'])
    index = ['scheduled', 'in_progress', 'complete', 'overdue'].index(current)
    options = [current]
    if index + 1 < len(['scheduled', 'in_progress', 'complete', 'overdue']):
        options.append(['scheduled', 'in_progress', 'complete', 'overdue'][index + 1])
    if index > 0:
        options.append(['scheduled', 'in_progress', 'complete', 'overdue'][index - 1])
    unique = []
    for item in options:
        if item not in unique:
            unique.append(item)
    return unique


def access_reviews_operator_actions(row: dict[str, Any]) -> list[dict[str, str]]:
    actions = [{'code': 'edit', 'label': 'Edit record'}]
    for status in access_reviews_next_statuses(str(row.get('status') or '')):
        actions.append({'code': 'status:' + status, 'label': 'Move to ' + status})
    if access_reviews_can_delete(row):
        actions.append({'code': 'delete', 'label': 'Remove record'})
    return actions


def access_reviews_toast(action: str, ok: bool) -> str:
    if ok:
        return f'Access Reviews {action} completed.'
    return f'Access Reviews {action} was blocked by policy.'


def access_reviews_dashboard_chip(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'key': 'access_reviews',
        'title': 'Access Reviews',
        'count': len(rows),
        'hot': len([row for row in rows if int(row.get('health_score') or 0) < 45]),
    }

def access_reviews_form_help_campaign() -> str:
    return 'Enter Campaign for Access Reviews. Local validation runs on save.'


def access_reviews_form_help_scope() -> str:
    return 'Enter Scope for Access Reviews. Local validation runs on save.'


def access_reviews_form_help_reviewer() -> str:
    return 'Enter Reviewer for Access Reviews. Local validation runs on save.'


def access_reviews_form_help_due_on() -> str:
    return 'Enter Due On for Access Reviews. Local validation runs on save.'


def access_reviews_form_help_item_count() -> str:
    return 'Enter Item Count for Access Reviews. Local validation runs on save.'


def access_reviews_form_help_status() -> str:
    return 'Enter Status for Access Reviews. Local validation runs on save.'


FORM_HELP_ACCESS_REVIEWS = {
    'campaign': access_reviews_form_help_campaign(),
    'scope': access_reviews_form_help_scope(),
    'reviewer': access_reviews_form_help_reviewer(),
    'due_on': access_reviews_form_help_due_on(),
    'item_count': access_reviews_form_help_item_count(),
    'status': access_reviews_form_help_status(),
}


def access_reviews_form_help() -> dict[str, str]:
    return dict(FORM_HELP_ACCESS_REVIEWS)

