"""Application service for Campaign Studio writes and operator actions."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.domains.campaigns.engine import engine
from app.domains.campaigns.policies import campaigns_gate_transition, campaigns_policy_card, campaigns_run_field_checks
from app.domains.campaigns.queries import campaigns_diff, campaigns_export_map
from app.domains.campaigns.reports import build_campaigns_reporter


class CampaignsService:
    """Coordinates validation, policy, persistence, and briefings for Campaign Studio."""

    def list_view(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        rows = engine.list_records(filters)
        reporter = build_campaigns_reporter(rows)
        return {
            'rows': rows,
            'kpis': engine.kpi_pack(),
            'pack': reporter.pack(),
        }

    def detail_view(self, record_id: str) -> dict[str, Any] | None:
        row = engine.get(record_id)
        if row is None:
            return None
        card = campaigns_policy_card(row)
        return {'record': row, 'policy': card}

    def create_from_form(self, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        field_errors = campaigns_run_field_checks(payload)
        if field_errors:
            return None, field_errors
        return engine.create(payload)

    def update_from_form(self, record_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        merged = deepcopy(current)
        merged.update(payload)
        field_errors = campaigns_run_field_checks(merged)
        if field_errors:
            return None, field_errors
        row, errors = engine.update(record_id, payload)
        if row:
            row['_diff'] = campaigns_diff(current, row)
        return row, errors

    def move_status(self, record_id: str, new_status: str) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        errors = campaigns_gate_transition(str(current.get('status') or ''), new_status)
        if errors:
            return None, errors
        return engine.transition(record_id, new_status)

    def export_maps(self) -> list[dict[str, str]]:
        return [campaigns_export_map(row) for row in engine.list_records()]

    def seed_if_empty(self, count: int = 10) -> int:
        return engine.seed_demo(count)


service = CampaignsService()


def campaigns_safe_payload(form: dict[str, Any]) -> dict[str, Any]:
    allowed = {name for name in ['campaign_name', 'channel', 'budget_cents', 'starts_on', 'ends_on', 'status']}
    clean = {}
    for name, value in form.items():
        if name in allowed or name in {'id', 'status'}:
            clean[name] = value
    return clean


def campaigns_can_delete(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status == 'planned':
        return True
    return int(row.get('health_score') or 0) < 20


def campaigns_next_statuses(current: str) -> list[str]:
    if current not in ['planned', 'live', 'paused', 'complete']:
        return list(['planned', 'live', 'paused', 'complete'])
    index = ['planned', 'live', 'paused', 'complete'].index(current)
    options = [current]
    if index + 1 < len(['planned', 'live', 'paused', 'complete']):
        options.append(['planned', 'live', 'paused', 'complete'][index + 1])
    if index > 0:
        options.append(['planned', 'live', 'paused', 'complete'][index - 1])
    unique = []
    for item in options:
        if item not in unique:
            unique.append(item)
    return unique


def campaigns_operator_actions(row: dict[str, Any]) -> list[dict[str, str]]:
    actions = [{'code': 'edit', 'label': 'Edit record'}]
    for status in campaigns_next_statuses(str(row.get('status') or '')):
        actions.append({'code': 'status:' + status, 'label': 'Move to ' + status})
    if campaigns_can_delete(row):
        actions.append({'code': 'delete', 'label': 'Remove record'})
    return actions


def campaigns_toast(action: str, ok: bool) -> str:
    if ok:
        return f'Campaign Studio {action} completed.'
    return f'Campaign Studio {action} was blocked by policy.'


def campaigns_dashboard_chip(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'key': 'campaigns',
        'title': 'Campaign Studio',
        'count': len(rows),
        'hot': len([row for row in rows if int(row.get('health_score') or 0) < 45]),
    }

def campaigns_form_help_campaign_name() -> str:
    return 'Enter Campaign Name for Campaign Studio. Local validation runs on save.'


def campaigns_form_help_channel() -> str:
    return 'Enter Channel for Campaign Studio. Local validation runs on save.'


def campaigns_form_help_budget_cents() -> str:
    return 'Enter Budget Cents for Campaign Studio. Local validation runs on save.'


def campaigns_form_help_starts_on() -> str:
    return 'Enter Starts On for Campaign Studio. Local validation runs on save.'


def campaigns_form_help_ends_on() -> str:
    return 'Enter Ends On for Campaign Studio. Local validation runs on save.'


def campaigns_form_help_status() -> str:
    return 'Enter Status for Campaign Studio. Local validation runs on save.'


FORM_HELP_CAMPAIGNS = {
    'campaign_name': campaigns_form_help_campaign_name(),
    'channel': campaigns_form_help_channel(),
    'budget_cents': campaigns_form_help_budget_cents(),
    'starts_on': campaigns_form_help_starts_on(),
    'ends_on': campaigns_form_help_ends_on(),
    'status': campaigns_form_help_status(),
}


def campaigns_form_help() -> dict[str, str]:
    return dict(FORM_HELP_CAMPAIGNS)

