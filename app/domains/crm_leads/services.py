"""Application service for Lead Inbox writes and operator actions."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.domains.crm_leads.engine import engine
from app.domains.crm_leads.policies import crm_leads_gate_transition, crm_leads_policy_card, crm_leads_run_field_checks
from app.domains.crm_leads.queries import crm_leads_diff, crm_leads_export_map
from app.domains.crm_leads.reports import build_crm_leads_reporter


class CrmLeadsService:
    """Coordinates validation, policy, persistence, and briefings for Lead Inbox."""

    def list_view(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        rows = engine.list_records(filters)
        reporter = build_crm_leads_reporter(rows)
        return {
            'rows': rows,
            'kpis': engine.kpi_pack(),
            'pack': reporter.pack(),
        }

    def detail_view(self, record_id: str) -> dict[str, Any] | None:
        row = engine.get(record_id)
        if row is None:
            return None
        card = crm_leads_policy_card(row)
        return {'record': row, 'policy': card}

    def create_from_form(self, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        field_errors = crm_leads_run_field_checks(payload)
        if field_errors:
            return None, field_errors
        return engine.create(payload)

    def update_from_form(self, record_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        merged = deepcopy(current)
        merged.update(payload)
        field_errors = crm_leads_run_field_checks(merged)
        if field_errors:
            return None, field_errors
        row, errors = engine.update(record_id, payload)
        if row:
            row['_diff'] = crm_leads_diff(current, row)
        return row, errors

    def move_status(self, record_id: str, new_status: str) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        errors = crm_leads_gate_transition(str(current.get('status') or ''), new_status)
        if errors:
            return None, errors
        return engine.transition(record_id, new_status)

    def export_maps(self) -> list[dict[str, str]]:
        return [crm_leads_export_map(row) for row in engine.list_records()]

    def seed_if_empty(self, count: int = 10) -> int:
        return engine.seed_demo(count)


service = CrmLeadsService()


def crm_leads_safe_payload(form: dict[str, Any]) -> dict[str, Any]:
    allowed = {name for name in ['company', 'contact', 'source', 'score', 'owner', 'status']}
    clean = {}
    for name, value in form.items():
        if name in allowed or name in {'id', 'status'}:
            clean[name] = value
    return clean


def crm_leads_can_delete(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status == 'new':
        return True
    return int(row.get('health_score') or 0) < 20


def crm_leads_next_statuses(current: str) -> list[str]:
    if current not in ['new', 'working', 'qualified', 'disqualified']:
        return list(['new', 'working', 'qualified', 'disqualified'])
    index = ['new', 'working', 'qualified', 'disqualified'].index(current)
    options = [current]
    if index + 1 < len(['new', 'working', 'qualified', 'disqualified']):
        options.append(['new', 'working', 'qualified', 'disqualified'][index + 1])
    if index > 0:
        options.append(['new', 'working', 'qualified', 'disqualified'][index - 1])
    unique = []
    for item in options:
        if item not in unique:
            unique.append(item)
    return unique


def crm_leads_operator_actions(row: dict[str, Any]) -> list[dict[str, str]]:
    actions = [{'code': 'edit', 'label': 'Edit record'}]
    for status in crm_leads_next_statuses(str(row.get('status') or '')):
        actions.append({'code': 'status:' + status, 'label': 'Move to ' + status})
    if crm_leads_can_delete(row):
        actions.append({'code': 'delete', 'label': 'Remove record'})
    return actions


def crm_leads_toast(action: str, ok: bool) -> str:
    if ok:
        return f'Lead Inbox {action} completed.'
    return f'Lead Inbox {action} was blocked by policy.'


def crm_leads_dashboard_chip(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'key': 'crm_leads',
        'title': 'Lead Inbox',
        'count': len(rows),
        'hot': len([row for row in rows if int(row.get('health_score') or 0) < 45]),
    }

def crm_leads_form_help_company() -> str:
    return 'Enter Company for Lead Inbox. Local validation runs on save.'


def crm_leads_form_help_contact() -> str:
    return 'Enter Contact for Lead Inbox. Local validation runs on save.'


def crm_leads_form_help_source() -> str:
    return 'Enter Source for Lead Inbox. Local validation runs on save.'


def crm_leads_form_help_score() -> str:
    return 'Enter Score for Lead Inbox. Local validation runs on save.'


def crm_leads_form_help_owner() -> str:
    return 'Enter Owner for Lead Inbox. Local validation runs on save.'


def crm_leads_form_help_status() -> str:
    return 'Enter Status for Lead Inbox. Local validation runs on save.'


FORM_HELP_CRM_LEADS = {
    'company': crm_leads_form_help_company(),
    'contact': crm_leads_form_help_contact(),
    'source': crm_leads_form_help_source(),
    'score': crm_leads_form_help_score(),
    'owner': crm_leads_form_help_owner(),
    'status': crm_leads_form_help_status(),
}


def crm_leads_form_help() -> dict[str, str]:
    return dict(FORM_HELP_CRM_LEADS)

