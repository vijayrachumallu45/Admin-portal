"""Application service for Opportunity Board writes and operator actions."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.domains.opportunities.engine import engine
from app.domains.opportunities.policies import opportunities_gate_transition, opportunities_policy_card, opportunities_run_field_checks
from app.domains.opportunities.queries import opportunities_diff, opportunities_export_map
from app.domains.opportunities.reports import build_opportunities_reporter


class OpportunitiesService:
    """Coordinates validation, policy, persistence, and briefings for Opportunity Board."""

    def list_view(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        rows = engine.list_records(filters)
        reporter = build_opportunities_reporter(rows)
        return {
            'rows': rows,
            'kpis': engine.kpi_pack(),
            'pack': reporter.pack(),
        }

    def detail_view(self, record_id: str) -> dict[str, Any] | None:
        row = engine.get(record_id)
        if row is None:
            return None
        card = opportunities_policy_card(row)
        return {'record': row, 'policy': card}

    def create_from_form(self, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        field_errors = opportunities_run_field_checks(payload)
        if field_errors:
            return None, field_errors
        return engine.create(payload)

    def update_from_form(self, record_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        merged = deepcopy(current)
        merged.update(payload)
        field_errors = opportunities_run_field_checks(merged)
        if field_errors:
            return None, field_errors
        row, errors = engine.update(record_id, payload)
        if row:
            row['_diff'] = opportunities_diff(current, row)
        return row, errors

    def move_status(self, record_id: str, new_status: str) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        errors = opportunities_gate_transition(str(current.get('status') or ''), new_status)
        if errors:
            return None, errors
        return engine.transition(record_id, new_status)

    def export_maps(self) -> list[dict[str, str]]:
        return [opportunities_export_map(row) for row in engine.list_records()]

    def seed_if_empty(self, count: int = 10) -> int:
        return engine.seed_demo(count)


service = OpportunitiesService()


def opportunities_safe_payload(form: dict[str, Any]) -> dict[str, Any]:
    allowed = {name for name in ['deal_name', 'account_name', 'amount_cents', 'stage', 'close_on', 'status']}
    clean = {}
    for name, value in form.items():
        if name in allowed or name in {'id', 'status'}:
            clean[name] = value
    return clean


def opportunities_can_delete(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status == 'open':
        return True
    return int(row.get('health_score') or 0) < 20


def opportunities_next_statuses(current: str) -> list[str]:
    if current not in ['open', 'won', 'lost']:
        return list(['open', 'won', 'lost'])
    index = ['open', 'won', 'lost'].index(current)
    options = [current]
    if index + 1 < len(['open', 'won', 'lost']):
        options.append(['open', 'won', 'lost'][index + 1])
    if index > 0:
        options.append(['open', 'won', 'lost'][index - 1])
    unique = []
    for item in options:
        if item not in unique:
            unique.append(item)
    return unique


def opportunities_operator_actions(row: dict[str, Any]) -> list[dict[str, str]]:
    actions = [{'code': 'edit', 'label': 'Edit record'}]
    for status in opportunities_next_statuses(str(row.get('status') or '')):
        actions.append({'code': 'status:' + status, 'label': 'Move to ' + status})
    if opportunities_can_delete(row):
        actions.append({'code': 'delete', 'label': 'Remove record'})
    return actions


def opportunities_toast(action: str, ok: bool) -> str:
    if ok:
        return f'Opportunity Board {action} completed.'
    return f'Opportunity Board {action} was blocked by policy.'


def opportunities_dashboard_chip(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'key': 'opportunities',
        'title': 'Opportunity Board',
        'count': len(rows),
        'hot': len([row for row in rows if int(row.get('health_score') or 0) < 45]),
    }

def opportunities_form_help_deal_name() -> str:
    return 'Enter Deal Name for Opportunity Board. Local validation runs on save.'


def opportunities_form_help_account_name() -> str:
    return 'Enter Account Name for Opportunity Board. Local validation runs on save.'


def opportunities_form_help_amount_cents() -> str:
    return 'Enter Amount Cents for Opportunity Board. Local validation runs on save.'


def opportunities_form_help_stage() -> str:
    return 'Enter Stage for Opportunity Board. Local validation runs on save.'


def opportunities_form_help_close_on() -> str:
    return 'Enter Close On for Opportunity Board. Local validation runs on save.'


def opportunities_form_help_status() -> str:
    return 'Enter Status for Opportunity Board. Local validation runs on save.'


FORM_HELP_OPPORTUNITIES = {
    'deal_name': opportunities_form_help_deal_name(),
    'account_name': opportunities_form_help_account_name(),
    'amount_cents': opportunities_form_help_amount_cents(),
    'stage': opportunities_form_help_stage(),
    'close_on': opportunities_form_help_close_on(),
    'status': opportunities_form_help_status(),
}


def opportunities_form_help() -> dict[str, str]:
    return dict(FORM_HELP_OPPORTUNITIES)

