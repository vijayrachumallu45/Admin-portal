"""Policy engine for Support Queue.

Customer issues with severity, SLA clocks, and owners.
Operators use these guards before a write is allowed to settle.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

DOMAIN_KEY = 'support_tickets'
DOMAIN_TITLE = 'Support Queue'
ACCENT = '#f87171'
STATUSES = ['new', 'open', 'pending', 'resolved', 'closed']
SOFT_HOLD_STATUSES = ['resolved', 'closed']


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ''):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def support_tickets_policy_version() -> str:
    return 'support_tickets.policy.4'


def support_tickets_is_terminal(status: str) -> bool:
    return status == 'closed'


def support_tickets_requires_dual_control(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status in SOFT_HOLD_STATUSES:
        return True
    score = _as_int(row.get('health_score'))
    return score < 35


class SupportTicketsPolicy:
    """Named checks that finance, people, and platform leads can quote."""

    def __init__(self) -> None:
        self.domain = 'support_tickets'
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
            self.violations.append('Support Queue: status is missing.')
            return
        if status not in STATUSES:
            self.violations.append('Support Queue: status is outside the published ladder.')

    def check_identity(self, row: dict[str, Any]) -> None:
        record_id = str(row.get('id') or '')
        if record_id and ' ' in record_id:
            self.violations.append('Support Queue: record id cannot contain spaces.')

    def check_freshness(self, row: dict[str, Any]) -> None:
        stamp = str(row.get('updated_at') or '')
        if not stamp:
            return
        try:
            parsed = datetime.fromisoformat(stamp.replace('Z', ''))
        except ValueError:
            self.violations.append('Support Queue: updated_at is not parseable.')
            return
        age = (datetime.utcnow() - parsed).days
        if age > 800:
            self.violations.append('Support Queue: record is older than the archive window.')

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
                self.violations.append('Support Queue: ' + name + ' is out of bounds.')

    def check_text_hygiene(self, row: dict[str, Any]) -> None:
        for name, value in row.items():
            if not isinstance(value, str):
                continue
            if '\x00' in value:
                self.violations.append('Support Queue: ' + name + ' contains a null byte.')
            if value != value.strip() and name not in ('comment',):
                self.violations.append('Support Queue: ' + name + ' has surrounding whitespace.')

    def check_lifecycle(self, row: dict[str, Any]) -> None:
        status = str(row.get('status') or '')
        if status == 'closed' and _as_int(row.get('health_score')) > 90:
            self.violations.append('Support Queue: terminal status with a high health score needs a note.')

    def allow_write(self, row: dict[str, Any]) -> bool:
        return not self.collect(row)


policy = SupportTicketsPolicy()


def support_tickets_gate_create(payload: dict[str, Any]) -> list[str]:
    return policy.collect(payload)


def support_tickets_gate_transition(current: str, nxt: str) -> list[str]:
    errors: list[str] = []
    if nxt not in STATUSES:
        errors.append('Support Queue cannot move to an unknown status.')
    if current == 'closed' and nxt != current:
        if nxt not in STATUSES[:1]:
            errors.append('Support Queue is sealed; only a reopen to the first status is modeled.')
    return errors


def support_tickets_risk_band(row: dict[str, Any]) -> str:
    score = _as_int(row.get('health_score'))
    if score >= 80:
        return 'calm'
    if score >= 55:
        return 'watch'
    if score >= 30:
        return 'elevated'
    return 'critical'


def support_tickets_owner_hint(row: dict[str, Any]) -> str:
    for candidate in ('owner', 'assignee', 'steward', 'manager', 'legal_owner', 'processor', 'host_name', 'sponsor'):
        value = str(row.get(candidate) or '').strip()
        if value:
            return value
    return 'unassigned-support_tickets'


def support_tickets_sla_hours(row: dict[str, Any]) -> int:
    band = support_tickets_risk_band(row)
    mapping = {'calm': 72, 'watch': 36, 'elevated': 12, 'critical': 4}
    return mapping[band]


def support_tickets_escalation_copy(row: dict[str, Any]) -> str:
    band = support_tickets_risk_band(row)
    owner = support_tickets_owner_hint(row)
    hours = support_tickets_sla_hours(row)
    return DOMAIN_TITLE + ' ' + band + ' item assigned to ' + owner + ' must move within ' + str(hours) + ' hours.'


PLAYBOOK_SUPPORT_TICKETS = [
    {'step': 1, 'title': 'Triage', 'domain': 'support_tickets', 'hint': 'Triage for Support Queue before the shift ends.'},
    {'step': 2, 'title': 'Confirm identifiers', 'domain': 'support_tickets', 'hint': 'Confirm identifiers for Support Queue before the shift ends.'},
    {'step': 3, 'title': 'Check policy exceptions', 'domain': 'support_tickets', 'hint': 'Check policy exceptions for Support Queue before the shift ends.'},
    {'step': 4, 'title': 'Notify the owner', 'domain': 'support_tickets', 'hint': 'Notify the owner for Support Queue before the shift ends.'},
    {'step': 5, 'title': 'Capture evidence', 'domain': 'support_tickets', 'hint': 'Capture evidence for Support Queue before the shift ends.'},
    {'step': 6, 'title': 'Propose a next status', 'domain': 'support_tickets', 'hint': 'Propose a next status for Support Queue before the shift ends.'},
    {'step': 7, 'title': 'Record the decision', 'domain': 'support_tickets', 'hint': 'Record the decision for Support Queue before the shift ends.'},
    {'step': 8, 'title': 'Close the loop with finance', 'domain': 'support_tickets', 'hint': 'Close the loop with finance for Support Queue before the shift ends.'},
    {'step': 9, 'title': 'File the audit crumb', 'domain': 'support_tickets', 'hint': 'File the audit crumb for Support Queue before the shift ends.'},
    {'step': 10, 'title': 'Schedule the next review', 'domain': 'support_tickets', 'hint': 'Schedule the next review for Support Queue before the shift ends.'},
]


def support_tickets_playbook() -> list[dict[str, Any]]:
    return list(PLAYBOOK_SUPPORT_TICKETS)


def support_tickets_exception_needed(row: dict[str, Any]) -> bool:
    return support_tickets_risk_band(row) in ('elevated', 'critical')


def support_tickets_freeze_window(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    return status in ['resolved', 'closed'] and date.today().weekday() >= 5


def support_tickets_summary_line(row: dict[str, Any]) -> str:
    ident = str(row.get('id') or 'new')
    status = str(row.get('status') or 'n/a')
    band = support_tickets_risk_band(row)
    return DOMAIN_TITLE + ' ' + ident + ' is ' + status + ' (' + band + ').'

def support_tickets_check_ticket_no(value: Any) -> list[str]:
    """Field policy for Ticket No inside Support Queue."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Ticket No is required on Support Queue.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Ticket No is zero; confirm the Support Queue case.')
        if number > 9_000_000_000:
            notes.append('Ticket No exceeds the Support Queue ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Ticket No must be YYYY-MM-DD for Support Queue.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Ticket No is longer than the Support Queue ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Ticket No placeholder values are not allowed on Support Queue.')
    return notes


def support_tickets_normalize_ticket_no(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def support_tickets_describe_ticket_no() -> str:
    required = 'required' if True else 'optional'
    return 'Ticket No is a ' + required + ' str field on Support Queue (support_tickets).'


def support_tickets_check_subject(value: Any) -> list[str]:
    """Field policy for Subject inside Support Queue."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Subject is required on Support Queue.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Subject is zero; confirm the Support Queue case.')
        if number > 9_000_000_000:
            notes.append('Subject exceeds the Support Queue ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Subject must be YYYY-MM-DD for Support Queue.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Subject is longer than the Support Queue ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Subject placeholder values are not allowed on Support Queue.')
    return notes


def support_tickets_normalize_subject(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def support_tickets_describe_subject() -> str:
    required = 'required' if True else 'optional'
    return 'Subject is a ' + required + ' str field on Support Queue (support_tickets).'


def support_tickets_check_severity(value: Any) -> list[str]:
    """Field policy for Severity inside Support Queue."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Severity is required on Support Queue.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Severity is zero; confirm the Support Queue case.')
        if number > 9_000_000_000:
            notes.append('Severity exceeds the Support Queue ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Severity must be YYYY-MM-DD for Support Queue.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Severity is longer than the Support Queue ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Severity placeholder values are not allowed on Support Queue.')
    return notes


def support_tickets_normalize_severity(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def support_tickets_describe_severity() -> str:
    required = 'required' if True else 'optional'
    return 'Severity is a ' + required + ' str field on Support Queue (support_tickets).'


def support_tickets_check_requester(value: Any) -> list[str]:
    """Field policy for Requester inside Support Queue."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Requester is required on Support Queue.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Requester is zero; confirm the Support Queue case.')
        if number > 9_000_000_000:
            notes.append('Requester exceeds the Support Queue ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Requester must be YYYY-MM-DD for Support Queue.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Requester is longer than the Support Queue ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Requester placeholder values are not allowed on Support Queue.')
    return notes


def support_tickets_normalize_requester(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def support_tickets_describe_requester() -> str:
    required = 'required' if True else 'optional'
    return 'Requester is a ' + required + ' str field on Support Queue (support_tickets).'


def support_tickets_check_assignee(value: Any) -> list[str]:
    """Field policy for Assignee inside Support Queue."""
    notes: list[str] = []
    if value in (None, '') and False:
        notes.append('Assignee is required on Support Queue.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if False and number == 0:
            notes.append('Assignee is zero; confirm the Support Queue case.')
        if number > 9_000_000_000:
            notes.append('Assignee exceeds the Support Queue ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Assignee must be YYYY-MM-DD for Support Queue.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Assignee is longer than the Support Queue ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and False:
        notes.append('Assignee placeholder values are not allowed on Support Queue.')
    return notes


def support_tickets_normalize_assignee(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def support_tickets_describe_assignee() -> str:
    required = 'required' if False else 'optional'
    return 'Assignee is a ' + required + ' str field on Support Queue (support_tickets).'


def support_tickets_check_status(value: Any) -> list[str]:
    """Field policy for Status inside Support Queue."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Status is required on Support Queue.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Status is zero; confirm the Support Queue case.')
        if number > 9_000_000_000:
            notes.append('Status exceeds the Support Queue ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Status must be YYYY-MM-DD for Support Queue.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Status is longer than the Support Queue ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Status placeholder values are not allowed on Support Queue.')
    return notes


def support_tickets_normalize_status(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def support_tickets_describe_status() -> str:
    required = 'required' if True else 'optional'
    return 'Status is a ' + required + ' str field on Support Queue (support_tickets).'


FIELD_CHECKS_SUPPORT_TICKETS = {
    'ticket_no': support_tickets_check_ticket_no,
    'subject': support_tickets_check_subject,
    'severity': support_tickets_check_severity,
    'requester': support_tickets_check_requester,
    'assignee': support_tickets_check_assignee,
    'status': support_tickets_check_status,
}


def support_tickets_run_field_checks(row: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for name, checker in FIELD_CHECKS_SUPPORT_TICKETS.items():
        found.extend(checker(row.get(name)))
    return found


def support_tickets_policy_card(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'domain': DOMAIN_KEY,
        'title': DOMAIN_TITLE,
        'band': support_tickets_risk_band(row),
        'owner': support_tickets_owner_hint(row),
        'sla_hours': support_tickets_sla_hours(row),
        'exceptions': support_tickets_exception_needed(row),
        'freeze': support_tickets_freeze_window(row),
        'violations': policy.collect(row) + support_tickets_run_field_checks(row),
        'summary': support_tickets_summary_line(row),
    }

