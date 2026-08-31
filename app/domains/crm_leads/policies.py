"""Policy engine for Lead Inbox.

Inbound interest with scoring, source, and routing.
Operators use these guards before a write is allowed to settle.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

DOMAIN_KEY = 'crm_leads'
DOMAIN_TITLE = 'Lead Inbox'
ACCENT = '#fb7185'
STATUSES = ['new', 'working', 'qualified', 'disqualified']
SOFT_HOLD_STATUSES = ['qualified', 'disqualified']


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ''):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def crm_leads_policy_version() -> str:
    return 'crm_leads.policy.4'


def crm_leads_is_terminal(status: str) -> bool:
    return status == 'disqualified'


def crm_leads_requires_dual_control(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status in SOFT_HOLD_STATUSES:
        return True
    score = _as_int(row.get('health_score'))
    return score < 35


class CrmLeadsPolicy:
    """Named checks that finance, people, and platform leads can quote."""

    def __init__(self) -> None:
        self.domain = 'crm_leads'
        self.violations: list[str] = []

    def reset(self) -> None:
        self.violations = []

    def collect(self, row: dict[str, Any]) -> list[str]:
        self.reset()
        self.check_status(row)
        self.check_identity(row)
        self.check_freshness(row)
        self.check_numeric_bounds(row)
        self.check_text_hygiene(row)
        self.check_lifecycle(row)
        return list(self.violations)

    def check_status(self, row: dict[str, Any]) -> None:
        status = str(row.get('status') or '')
        if not status:
            self.violations.append('Lead Inbox: status is missing.')
            return
        if status not in STATUSES:
            self.violations.append('Lead Inbox: status is outside the published ladder.')

    def check_identity(self, row: dict[str, Any]) -> None:
        record_id = str(row.get('id') or '')
        if record_id and ' ' in record_id:
            self.violations.append('Lead Inbox: record id cannot contain spaces.')

    def check_freshness(self, row: dict[str, Any]) -> None:
        stamp = str(row.get('updated_at') or '')
        if not stamp:
            return
        try:
            parsed = datetime.fromisoformat(stamp.replace('Z', ''))
        except ValueError:
            self.violations.append('Lead Inbox: updated_at is not parseable.')
            return
        age = (datetime.utcnow() - parsed).days
        if age > 800:
            self.violations.append('Lead Inbox: record is older than the archive window.')

    def check_numeric_bounds(self, row: dict[str, Any]) -> None:
        for name, value in row.items():
            if not name.endswith('_cents') and name not in (
                'health_score',
                'seats',
                'minutes',
                'days',
                'percent',
                'score',
                'cap',
                'headcount',
            ):
                continue
            number = _as_int(value, default=-1)
            if number < 0:
                self.violations.append('Lead Inbox: ' + name + ' is out of bounds.')

    def check_text_hygiene(self, row: dict[str, Any]) -> None:
        for name, value in row.items():
            if not isinstance(value, str):
                continue
            if '\x00' in value:
                self.violations.append('Lead Inbox: ' + name + ' contains a null byte.')
            if value != value.strip() and name not in ('comment',):
                self.violations.append('Lead Inbox: ' + name + ' has surrounding whitespace.')

    def check_lifecycle(self, row: dict[str, Any]) -> None:
        status = str(row.get('status') or '')
        if status == 'disqualified' and _as_int(row.get('health_score')) > 90:
            self.violations.append('Lead Inbox: terminal status with a high health score needs a note.')

    def allow_write(self, row: dict[str, Any]) -> bool:
        return not self.collect(row)


policy = CrmLeadsPolicy()


def crm_leads_gate_create(payload: dict[str, Any]) -> list[str]:
    return policy.collect(payload)


def crm_leads_gate_transition(current: str, nxt: str) -> list[str]:
    errors: list[str] = []
    if nxt not in STATUSES:
        errors.append('Lead Inbox cannot move to an unknown status.')
    if current == 'disqualified' and nxt != current:
        if nxt not in STATUSES[:1]:
            errors.append('Lead Inbox is sealed; only a reopen to the first status is modeled.')
    return errors


def crm_leads_risk_band(row: dict[str, Any]) -> str:
    score = _as_int(row.get('health_score'))
    if score >= 80:
        return 'calm'
    if score >= 55:
        return 'watch'
    if score >= 30:
        return 'elevated'
    return 'critical'


def crm_leads_owner_hint(row: dict[str, Any]) -> str:
    for candidate in ('owner', 'assignee', 'steward', 'manager', 'legal_owner', 'processor', 'host_name', 'sponsor'):
        value = str(row.get(candidate) or '').strip()
        if value:
            return value
    return 'unassigned-crm_leads'


def crm_leads_sla_hours(row: dict[str, Any]) -> int:
    band = crm_leads_risk_band(row)
    mapping = {'calm': 72, 'watch': 36, 'elevated': 12, 'critical': 4}
    return mapping[band]


def crm_leads_escalation_copy(row: dict[str, Any]) -> str:
    band = crm_leads_risk_band(row)
    owner = crm_leads_owner_hint(row)
    hours = crm_leads_sla_hours(row)
    return DOMAIN_TITLE + ' ' + band + ' item assigned to ' + owner + ' must move within ' + str(hours) + ' hours.'


PLAYBOOK_CRM_LEADS = [
    {'step': 1, 'title': 'Triage', 'domain': 'crm_leads', 'hint': 'Triage for Lead Inbox before the shift ends.'},
    {'step': 2, 'title': 'Confirm identifiers', 'domain': 'crm_leads', 'hint': 'Confirm identifiers for Lead Inbox before the shift ends.'},
    {'step': 3, 'title': 'Check policy exceptions', 'domain': 'crm_leads', 'hint': 'Check policy exceptions for Lead Inbox before the shift ends.'},
    {'step': 4, 'title': 'Notify the owner', 'domain': 'crm_leads', 'hint': 'Notify the owner for Lead Inbox before the shift ends.'},
    {'step': 5, 'title': 'Capture evidence', 'domain': 'crm_leads', 'hint': 'Capture evidence for Lead Inbox before the shift ends.'},
    {'step': 6, 'title': 'Propose a next status', 'domain': 'crm_leads', 'hint': 'Propose a next status for Lead Inbox before the shift ends.'},
    {'step': 7, 'title': 'Record the decision', 'domain': 'crm_leads', 'hint': 'Record the decision for Lead Inbox before the shift ends.'},
    {'step': 8, 'title': 'Close the loop with finance', 'domain': 'crm_leads', 'hint': 'Close the loop with finance for Lead Inbox before the shift ends.'},
    {'step': 9, 'title': 'File the audit crumb', 'domain': 'crm_leads', 'hint': 'File the audit crumb for Lead Inbox before the shift ends.'},
    {'step': 10, 'title': 'Schedule the next review', 'domain': 'crm_leads', 'hint': 'Schedule the next review for Lead Inbox before the shift ends.'},
]


def crm_leads_playbook() -> list[dict[str, Any]]:
    return list(PLAYBOOK_CRM_LEADS)


def crm_leads_exception_needed(row: dict[str, Any]) -> bool:
    return crm_leads_risk_band(row) in ('elevated', 'critical')


def crm_leads_freeze_window(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    return status in ['qualified', 'disqualified'] and date.today().weekday() >= 5


def crm_leads_summary_line(row: dict[str, Any]) -> str:
    ident = str(row.get('id') or 'new')
    status = str(row.get('status') or 'n/a')
    band = crm_leads_risk_band(row)
    return DOMAIN_TITLE + ' ' + ident + ' is ' + status + ' (' + band + ').'

def crm_leads_check_company(value: Any) -> list[str]:
    """Field policy for Company inside Lead Inbox."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Company is required on Lead Inbox.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Company is zero; confirm the Lead Inbox case.')
        if number > 9_000_000_000:
            notes.append('Company exceeds the Lead Inbox ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Company must be YYYY-MM-DD for Lead Inbox.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Company is longer than the Lead Inbox ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Company placeholder values are not allowed on Lead Inbox.')
    return notes


def crm_leads_normalize_company(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def crm_leads_describe_company() -> str:
    required = 'required' if True else 'optional'
    return 'Company is a ' + required + ' str field on Lead Inbox (crm_leads).'


def crm_leads_check_contact(value: Any) -> list[str]:
    """Field policy for Contact inside Lead Inbox."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Contact is required on Lead Inbox.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Contact is zero; confirm the Lead Inbox case.')
        if number > 9_000_000_000:
            notes.append('Contact exceeds the Lead Inbox ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Contact must be YYYY-MM-DD for Lead Inbox.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Contact is longer than the Lead Inbox ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Contact placeholder values are not allowed on Lead Inbox.')
    return notes


def crm_leads_normalize_contact(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def crm_leads_describe_contact() -> str:
    required = 'required' if True else 'optional'
    return 'Contact is a ' + required + ' str field on Lead Inbox (crm_leads).'


def crm_leads_check_source(value: Any) -> list[str]:
    """Field policy for Source inside Lead Inbox."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Source is required on Lead Inbox.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Source is zero; confirm the Lead Inbox case.')
        if number > 9_000_000_000:
            notes.append('Source exceeds the Lead Inbox ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Source must be YYYY-MM-DD for Lead Inbox.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Source is longer than the Lead Inbox ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Source placeholder values are not allowed on Lead Inbox.')
    return notes


def crm_leads_normalize_source(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def crm_leads_describe_source() -> str:
    required = 'required' if True else 'optional'
    return 'Source is a ' + required + ' str field on Lead Inbox (crm_leads).'


def crm_leads_check_score(value: Any) -> list[str]:
    """Field policy for Score inside Lead Inbox."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Score is required on Lead Inbox.')
        return notes
    if 'int' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Score is zero; confirm the Lead Inbox case.')
        if number > 9_000_000_000:
            notes.append('Score exceeds the Lead Inbox ceiling.')
        return notes
    if 'int' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Score must be YYYY-MM-DD for Lead Inbox.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Score is longer than the Lead Inbox ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Score placeholder values are not allowed on Lead Inbox.')
    return notes


def crm_leads_normalize_score(value: Any) -> Any:
    if 'int' == 'int':
        return _as_int(value)
    if 'int' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def crm_leads_describe_score() -> str:
    required = 'required' if True else 'optional'
    return 'Score is a ' + required + ' int field on Lead Inbox (crm_leads).'


def crm_leads_check_owner(value: Any) -> list[str]:
    """Field policy for Owner inside Lead Inbox."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Owner is required on Lead Inbox.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Owner is zero; confirm the Lead Inbox case.')
        if number > 9_000_000_000:
            notes.append('Owner exceeds the Lead Inbox ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Owner must be YYYY-MM-DD for Lead Inbox.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Owner is longer than the Lead Inbox ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Owner placeholder values are not allowed on Lead Inbox.')
    return notes


def crm_leads_normalize_owner(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def crm_leads_describe_owner() -> str:
    required = 'required' if True else 'optional'
    return 'Owner is a ' + required + ' str field on Lead Inbox (crm_leads).'


def crm_leads_check_status(value: Any) -> list[str]:
    """Field policy for Status inside Lead Inbox."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Status is required on Lead Inbox.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Status is zero; confirm the Lead Inbox case.')
        if number > 9_000_000_000:
            notes.append('Status exceeds the Lead Inbox ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Status must be YYYY-MM-DD for Lead Inbox.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Status is longer than the Lead Inbox ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Status placeholder values are not allowed on Lead Inbox.')
    return notes


def crm_leads_normalize_status(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def crm_leads_describe_status() -> str:
    required = 'required' if True else 'optional'
    return 'Status is a ' + required + ' str field on Lead Inbox (crm_leads).'


FIELD_CHECKS_CRM_LEADS = {
    'company': crm_leads_check_company,
    'contact': crm_leads_check_contact,
    'source': crm_leads_check_source,
    'score': crm_leads_check_score,
    'owner': crm_leads_check_owner,
    'status': crm_leads_check_status,
}


def crm_leads_run_field_checks(row: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for name, checker in FIELD_CHECKS_CRM_LEADS.items():
        found.extend(checker(row.get(name)))
    return found


def crm_leads_policy_card(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'domain': DOMAIN_KEY,
        'title': DOMAIN_TITLE,
        'band': crm_leads_risk_band(row),
        'owner': crm_leads_owner_hint(row),
        'sla_hours': crm_leads_sla_hours(row),
        'exceptions': crm_leads_exception_needed(row),
        'freeze': crm_leads_freeze_window(row),
        'violations': policy.collect(row) + crm_leads_run_field_checks(row),
        'summary': crm_leads_summary_line(row),
    }

