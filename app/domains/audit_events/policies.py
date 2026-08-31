"""Policy engine for Audit Ledger.

Immutable operator actions for investigations and compliance packs.
Operators use these guards before a write is allowed to settle.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

DOMAIN_KEY = 'audit_events'
DOMAIN_TITLE = 'Audit Ledger'
ACCENT = '#b388ff'
STATUSES = ['recorded', 'reviewed', 'escalated', 'closed']
SOFT_HOLD_STATUSES = ['escalated', 'closed']


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ''):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def audit_events_policy_version() -> str:
    return 'audit_events.policy.4'


def audit_events_is_terminal(status: str) -> bool:
    return status == 'closed'


def audit_events_requires_dual_control(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status in SOFT_HOLD_STATUSES:
        return True
    score = _as_int(row.get('health_score'))
    return score < 35


class AuditEventsPolicy:
    """Named checks that finance, people, and platform leads can quote."""

    def __init__(self) -> None:
        self.domain = 'audit_events'
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
            self.violations.append('Audit Ledger: status is missing.')
            return
        if status not in STATUSES:
            self.violations.append('Audit Ledger: status is outside the published ladder.')

    def check_identity(self, row: dict[str, Any]) -> None:
        record_id = str(row.get('id') or '')
        if record_id and ' ' in record_id:
            self.violations.append('Audit Ledger: record id cannot contain spaces.')

    def check_freshness(self, row: dict[str, Any]) -> None:
        stamp = str(row.get('updated_at') or '')
        if not stamp:
            return
        try:
            parsed = datetime.fromisoformat(stamp.replace('Z', ''))
        except ValueError:
            self.violations.append('Audit Ledger: updated_at is not parseable.')
            return
        age = (datetime.utcnow() - parsed).days
        if age > 800:
            self.violations.append('Audit Ledger: record is older than the archive window.')

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
                self.violations.append('Audit Ledger: ' + name + ' is out of bounds.')

    def check_text_hygiene(self, row: dict[str, Any]) -> None:
        for name, value in row.items():
            if not isinstance(value, str):
                continue
            if '\x00' in value:
                self.violations.append('Audit Ledger: ' + name + ' contains a null byte.')
            if value != value.strip() and name not in ('comment',):
                self.violations.append('Audit Ledger: ' + name + ' has surrounding whitespace.')

    def check_lifecycle(self, row: dict[str, Any]) -> None:
        status = str(row.get('status') or '')
        if status == 'closed' and _as_int(row.get('health_score')) > 90:
            self.violations.append('Audit Ledger: terminal status with a high health score needs a note.')

    def allow_write(self, row: dict[str, Any]) -> bool:
        return not self.collect(row)


policy = AuditEventsPolicy()


def audit_events_gate_create(payload: dict[str, Any]) -> list[str]:
    return policy.collect(payload)


def audit_events_gate_transition(current: str, nxt: str) -> list[str]:
    errors: list[str] = []
    if nxt not in STATUSES:
        errors.append('Audit Ledger cannot move to an unknown status.')
    if current == 'closed' and nxt != current:
        if nxt not in STATUSES[:1]:
            errors.append('Audit Ledger is sealed; only a reopen to the first status is modeled.')
    return errors


def audit_events_risk_band(row: dict[str, Any]) -> str:
    score = _as_int(row.get('health_score'))
    if score >= 80:
        return 'calm'
    if score >= 55:
        return 'watch'
    if score >= 30:
        return 'elevated'
    return 'critical'


def audit_events_owner_hint(row: dict[str, Any]) -> str:
    for candidate in ('owner', 'assignee', 'steward', 'manager', 'legal_owner', 'processor', 'host_name', 'sponsor'):
        value = str(row.get(candidate) or '').strip()
        if value:
            return value
    return 'unassigned-audit_events'


def audit_events_sla_hours(row: dict[str, Any]) -> int:
    band = audit_events_risk_band(row)
    mapping = {'calm': 72, 'watch': 36, 'elevated': 12, 'critical': 4}
    return mapping[band]


def audit_events_escalation_copy(row: dict[str, Any]) -> str:
    band = audit_events_risk_band(row)
    owner = audit_events_owner_hint(row)
    hours = audit_events_sla_hours(row)
    return DOMAIN_TITLE + ' ' + band + ' item assigned to ' + owner + ' must move within ' + str(hours) + ' hours.'


PLAYBOOK_AUDIT_EVENTS = [
    {'step': 1, 'title': 'Triage', 'domain': 'audit_events', 'hint': 'Triage for Audit Ledger before the shift ends.'},
    {'step': 2, 'title': 'Confirm identifiers', 'domain': 'audit_events', 'hint': 'Confirm identifiers for Audit Ledger before the shift ends.'},
    {'step': 3, 'title': 'Check policy exceptions', 'domain': 'audit_events', 'hint': 'Check policy exceptions for Audit Ledger before the shift ends.'},
    {'step': 4, 'title': 'Notify the owner', 'domain': 'audit_events', 'hint': 'Notify the owner for Audit Ledger before the shift ends.'},
    {'step': 5, 'title': 'Capture evidence', 'domain': 'audit_events', 'hint': 'Capture evidence for Audit Ledger before the shift ends.'},
    {'step': 6, 'title': 'Propose a next status', 'domain': 'audit_events', 'hint': 'Propose a next status for Audit Ledger before the shift ends.'},
    {'step': 7, 'title': 'Record the decision', 'domain': 'audit_events', 'hint': 'Record the decision for Audit Ledger before the shift ends.'},
    {'step': 8, 'title': 'Close the loop with finance', 'domain': 'audit_events', 'hint': 'Close the loop with finance for Audit Ledger before the shift ends.'},
    {'step': 9, 'title': 'File the audit crumb', 'domain': 'audit_events', 'hint': 'File the audit crumb for Audit Ledger before the shift ends.'},
    {'step': 10, 'title': 'Schedule the next review', 'domain': 'audit_events', 'hint': 'Schedule the next review for Audit Ledger before the shift ends.'},
]


def audit_events_playbook() -> list[dict[str, Any]]:
    return list(PLAYBOOK_AUDIT_EVENTS)


def audit_events_exception_needed(row: dict[str, Any]) -> bool:
    return audit_events_risk_band(row) in ('elevated', 'critical')


def audit_events_freeze_window(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    return status in ['escalated', 'closed'] and date.today().weekday() >= 5


def audit_events_summary_line(row: dict[str, Any]) -> str:
    ident = str(row.get('id') or 'new')
    status = str(row.get('status') or 'n/a')
    band = audit_events_risk_band(row)
    return DOMAIN_TITLE + ' ' + ident + ' is ' + status + ' (' + band + ').'

def audit_events_check_actor(value: Any) -> list[str]:
    """Field policy for Actor inside Audit Ledger."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Actor is required on Audit Ledger.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Actor is zero; confirm the Audit Ledger case.')
        if number > 9_000_000_000:
            notes.append('Actor exceeds the Audit Ledger ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Actor must be YYYY-MM-DD for Audit Ledger.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Actor is longer than the Audit Ledger ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Actor placeholder values are not allowed on Audit Ledger.')
    return notes


def audit_events_normalize_actor(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def audit_events_describe_actor() -> str:
    required = 'required' if True else 'optional'
    return 'Actor is a ' + required + ' str field on Audit Ledger (audit_events).'


def audit_events_check_action(value: Any) -> list[str]:
    """Field policy for Action inside Audit Ledger."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Action is required on Audit Ledger.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Action is zero; confirm the Audit Ledger case.')
        if number > 9_000_000_000:
            notes.append('Action exceeds the Audit Ledger ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Action must be YYYY-MM-DD for Audit Ledger.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Action is longer than the Audit Ledger ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Action placeholder values are not allowed on Audit Ledger.')
    return notes


def audit_events_normalize_action(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def audit_events_describe_action() -> str:
    required = 'required' if True else 'optional'
    return 'Action is a ' + required + ' str field on Audit Ledger (audit_events).'


def audit_events_check_resource(value: Any) -> list[str]:
    """Field policy for Resource inside Audit Ledger."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Resource is required on Audit Ledger.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Resource is zero; confirm the Audit Ledger case.')
        if number > 9_000_000_000:
            notes.append('Resource exceeds the Audit Ledger ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Resource must be YYYY-MM-DD for Audit Ledger.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Resource is longer than the Audit Ledger ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Resource placeholder values are not allowed on Audit Ledger.')
    return notes


def audit_events_normalize_resource(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def audit_events_describe_resource() -> str:
    required = 'required' if True else 'optional'
    return 'Resource is a ' + required + ' str field on Audit Ledger (audit_events).'


def audit_events_check_ip_hint(value: Any) -> list[str]:
    """Field policy for Ip Hint inside Audit Ledger."""
    notes: list[str] = []
    if value in (None, '') and False:
        notes.append('Ip Hint is required on Audit Ledger.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if False and number == 0:
            notes.append('Ip Hint is zero; confirm the Audit Ledger case.')
        if number > 9_000_000_000:
            notes.append('Ip Hint exceeds the Audit Ledger ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Ip Hint must be YYYY-MM-DD for Audit Ledger.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Ip Hint is longer than the Audit Ledger ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and False:
        notes.append('Ip Hint placeholder values are not allowed on Audit Ledger.')
    return notes


def audit_events_normalize_ip_hint(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def audit_events_describe_ip_hint() -> str:
    required = 'required' if False else 'optional'
    return 'Ip Hint is a ' + required + ' str field on Audit Ledger (audit_events).'


def audit_events_check_occurred_at(value: Any) -> list[str]:
    """Field policy for Occurred At inside Audit Ledger."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Occurred At is required on Audit Ledger.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Occurred At is zero; confirm the Audit Ledger case.')
        if number > 9_000_000_000:
            notes.append('Occurred At exceeds the Audit Ledger ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Occurred At must be YYYY-MM-DD for Audit Ledger.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Occurred At is longer than the Audit Ledger ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Occurred At placeholder values are not allowed on Audit Ledger.')
    return notes


def audit_events_normalize_occurred_at(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def audit_events_describe_occurred_at() -> str:
    required = 'required' if True else 'optional'
    return 'Occurred At is a ' + required + ' str field on Audit Ledger (audit_events).'


def audit_events_check_severity(value: Any) -> list[str]:
    """Field policy for Severity inside Audit Ledger."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Severity is required on Audit Ledger.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Severity is zero; confirm the Audit Ledger case.')
        if number > 9_000_000_000:
            notes.append('Severity exceeds the Audit Ledger ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Severity must be YYYY-MM-DD for Audit Ledger.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Severity is longer than the Audit Ledger ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Severity placeholder values are not allowed on Audit Ledger.')
    return notes


def audit_events_normalize_severity(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def audit_events_describe_severity() -> str:
    required = 'required' if True else 'optional'
    return 'Severity is a ' + required + ' str field on Audit Ledger (audit_events).'


def audit_events_check_status(value: Any) -> list[str]:
    """Field policy for Status inside Audit Ledger."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Status is required on Audit Ledger.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Status is zero; confirm the Audit Ledger case.')
        if number > 9_000_000_000:
            notes.append('Status exceeds the Audit Ledger ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Status must be YYYY-MM-DD for Audit Ledger.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Status is longer than the Audit Ledger ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Status placeholder values are not allowed on Audit Ledger.')
    return notes


def audit_events_normalize_status(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def audit_events_describe_status() -> str:
    required = 'required' if True else 'optional'
    return 'Status is a ' + required + ' str field on Audit Ledger (audit_events).'


FIELD_CHECKS_AUDIT_EVENTS = {
    'actor': audit_events_check_actor,
    'action': audit_events_check_action,
    'resource': audit_events_check_resource,
    'ip_hint': audit_events_check_ip_hint,
    'occurred_at': audit_events_check_occurred_at,
    'severity': audit_events_check_severity,
    'status': audit_events_check_status,
}


def audit_events_run_field_checks(row: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for name, checker in FIELD_CHECKS_AUDIT_EVENTS.items():
        found.extend(checker(row.get(name)))
    return found


def audit_events_policy_card(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'domain': DOMAIN_KEY,
        'title': DOMAIN_TITLE,
        'band': audit_events_risk_band(row),
        'owner': audit_events_owner_hint(row),
        'sla_hours': audit_events_sla_hours(row),
        'exceptions': audit_events_exception_needed(row),
        'freeze': audit_events_freeze_window(row),
        'violations': policy.collect(row) + audit_events_run_field_checks(row),
        'summary': audit_events_summary_line(row),
    }

