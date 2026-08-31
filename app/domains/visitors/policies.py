"""Policy engine for Visitor Desk.

Site guests with hosts, badges, and expected departure.
Operators use these guards before a write is allowed to settle.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

DOMAIN_KEY = 'visitors'
DOMAIN_TITLE = 'Visitor Desk'
ACCENT = '#fdba74'
STATUSES = ['expected', 'on_site', 'departed']
SOFT_HOLD_STATUSES = ['on_site', 'departed']


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ''):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def visitors_policy_version() -> str:
    return 'visitors.policy.4'


def visitors_is_terminal(status: str) -> bool:
    return status == 'departed'


def visitors_requires_dual_control(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status in SOFT_HOLD_STATUSES:
        return True
    score = _as_int(row.get('health_score'))
    return score < 35


class VisitorsPolicy:
    """Named checks that finance, people, and platform leads can quote."""

    def __init__(self) -> None:
        self.domain = 'visitors'
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
            self.violations.append('Visitor Desk: status is missing.')
            return
        if status not in STATUSES:
            self.violations.append('Visitor Desk: status is outside the published ladder.')

    def check_identity(self, row: dict[str, Any]) -> None:
        record_id = str(row.get('id') or '')
        if record_id and ' ' in record_id:
            self.violations.append('Visitor Desk: record id cannot contain spaces.')

    def check_freshness(self, row: dict[str, Any]) -> None:
        stamp = str(row.get('updated_at') or '')
        if not stamp:
            return
        try:
            parsed = datetime.fromisoformat(stamp.replace('Z', ''))
        except ValueError:
            self.violations.append('Visitor Desk: updated_at is not parseable.')
            return
        age = (datetime.utcnow() - parsed).days
        if age > 800:
            self.violations.append('Visitor Desk: record is older than the archive window.')

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
                self.violations.append('Visitor Desk: ' + name + ' is out of bounds.')

    def check_text_hygiene(self, row: dict[str, Any]) -> None:
        for name, value in row.items():
            if not isinstance(value, str):
                continue
            if '\x00' in value:
                self.violations.append('Visitor Desk: ' + name + ' contains a null byte.')
            if value != value.strip() and name not in ('comment',):
                self.violations.append('Visitor Desk: ' + name + ' has surrounding whitespace.')

    def check_lifecycle(self, row: dict[str, Any]) -> None:
        status = str(row.get('status') or '')
        if status == 'departed' and _as_int(row.get('health_score')) > 90:
            self.violations.append('Visitor Desk: terminal status with a high health score needs a note.')

    def allow_write(self, row: dict[str, Any]) -> bool:
        return not self.collect(row)


policy = VisitorsPolicy()


def visitors_gate_create(payload: dict[str, Any]) -> list[str]:
    return policy.collect(payload)


def visitors_gate_transition(current: str, nxt: str) -> list[str]:
    errors: list[str] = []
    if nxt not in STATUSES:
        errors.append('Visitor Desk cannot move to an unknown status.')
    if current == 'departed' and nxt != current:
        if nxt not in STATUSES[:1]:
            errors.append('Visitor Desk is sealed; only a reopen to the first status is modeled.')
    return errors


def visitors_risk_band(row: dict[str, Any]) -> str:
    score = _as_int(row.get('health_score'))
    if score >= 80:
        return 'calm'
    if score >= 55:
        return 'watch'
    if score >= 30:
        return 'elevated'
    return 'critical'


def visitors_owner_hint(row: dict[str, Any]) -> str:
    for candidate in ('owner', 'assignee', 'steward', 'manager', 'legal_owner', 'processor', 'host_name', 'sponsor'):
        value = str(row.get(candidate) or '').strip()
        if value:
            return value
    return 'unassigned-visitors'


def visitors_sla_hours(row: dict[str, Any]) -> int:
    band = visitors_risk_band(row)
    mapping = {'calm': 72, 'watch': 36, 'elevated': 12, 'critical': 4}
    return mapping[band]


def visitors_escalation_copy(row: dict[str, Any]) -> str:
    band = visitors_risk_band(row)
    owner = visitors_owner_hint(row)
    hours = visitors_sla_hours(row)
    return DOMAIN_TITLE + ' ' + band + ' item assigned to ' + owner + ' must move within ' + str(hours) + ' hours.'


PLAYBOOK_VISITORS = [
    {'step': 1, 'title': 'Triage', 'domain': 'visitors', 'hint': 'Triage for Visitor Desk before the shift ends.'},
    {'step': 2, 'title': 'Confirm identifiers', 'domain': 'visitors', 'hint': 'Confirm identifiers for Visitor Desk before the shift ends.'},
    {'step': 3, 'title': 'Check policy exceptions', 'domain': 'visitors', 'hint': 'Check policy exceptions for Visitor Desk before the shift ends.'},
    {'step': 4, 'title': 'Notify the owner', 'domain': 'visitors', 'hint': 'Notify the owner for Visitor Desk before the shift ends.'},
    {'step': 5, 'title': 'Capture evidence', 'domain': 'visitors', 'hint': 'Capture evidence for Visitor Desk before the shift ends.'},
    {'step': 6, 'title': 'Propose a next status', 'domain': 'visitors', 'hint': 'Propose a next status for Visitor Desk before the shift ends.'},
    {'step': 7, 'title': 'Record the decision', 'domain': 'visitors', 'hint': 'Record the decision for Visitor Desk before the shift ends.'},
    {'step': 8, 'title': 'Close the loop with finance', 'domain': 'visitors', 'hint': 'Close the loop with finance for Visitor Desk before the shift ends.'},
    {'step': 9, 'title': 'File the audit crumb', 'domain': 'visitors', 'hint': 'File the audit crumb for Visitor Desk before the shift ends.'},
    {'step': 10, 'title': 'Schedule the next review', 'domain': 'visitors', 'hint': 'Schedule the next review for Visitor Desk before the shift ends.'},
]


def visitors_playbook() -> list[dict[str, Any]]:
    return list(PLAYBOOK_VISITORS)


def visitors_exception_needed(row: dict[str, Any]) -> bool:
    return visitors_risk_band(row) in ('elevated', 'critical')


def visitors_freeze_window(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    return status in ['on_site', 'departed'] and date.today().weekday() >= 5


def visitors_summary_line(row: dict[str, Any]) -> str:
    ident = str(row.get('id') or 'new')
    status = str(row.get('status') or 'n/a')
    band = visitors_risk_band(row)
    return DOMAIN_TITLE + ' ' + ident + ' is ' + status + ' (' + band + ').'

def visitors_check_visitor_name(value: Any) -> list[str]:
    """Field policy for Visitor Name inside Visitor Desk."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Visitor Name is required on Visitor Desk.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Visitor Name is zero; confirm the Visitor Desk case.')
        if number > 9_000_000_000:
            notes.append('Visitor Name exceeds the Visitor Desk ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Visitor Name must be YYYY-MM-DD for Visitor Desk.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Visitor Name is longer than the Visitor Desk ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Visitor Name placeholder values are not allowed on Visitor Desk.')
    return notes


def visitors_normalize_visitor_name(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def visitors_describe_visitor_name() -> str:
    required = 'required' if True else 'optional'
    return 'Visitor Name is a ' + required + ' str field on Visitor Desk (visitors).'


def visitors_check_host_name(value: Any) -> list[str]:
    """Field policy for Host Name inside Visitor Desk."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Host Name is required on Visitor Desk.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Host Name is zero; confirm the Visitor Desk case.')
        if number > 9_000_000_000:
            notes.append('Host Name exceeds the Visitor Desk ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Host Name must be YYYY-MM-DD for Visitor Desk.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Host Name is longer than the Visitor Desk ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Host Name placeholder values are not allowed on Visitor Desk.')
    return notes


def visitors_normalize_host_name(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def visitors_describe_host_name() -> str:
    required = 'required' if True else 'optional'
    return 'Host Name is a ' + required + ' str field on Visitor Desk (visitors).'


def visitors_check_company(value: Any) -> list[str]:
    """Field policy for Company inside Visitor Desk."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Company is required on Visitor Desk.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Company is zero; confirm the Visitor Desk case.')
        if number > 9_000_000_000:
            notes.append('Company exceeds the Visitor Desk ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Company must be YYYY-MM-DD for Visitor Desk.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Company is longer than the Visitor Desk ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Company placeholder values are not allowed on Visitor Desk.')
    return notes


def visitors_normalize_company(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def visitors_describe_company() -> str:
    required = 'required' if True else 'optional'
    return 'Company is a ' + required + ' str field on Visitor Desk (visitors).'


def visitors_check_arrives_on(value: Any) -> list[str]:
    """Field policy for Arrives On inside Visitor Desk."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Arrives On is required on Visitor Desk.')
        return notes
    if 'date' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Arrives On is zero; confirm the Visitor Desk case.')
        if number > 9_000_000_000:
            notes.append('Arrives On exceeds the Visitor Desk ceiling.')
        return notes
    if 'date' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Arrives On must be YYYY-MM-DD for Visitor Desk.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Arrives On is longer than the Visitor Desk ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Arrives On placeholder values are not allowed on Visitor Desk.')
    return notes


def visitors_normalize_arrives_on(value: Any) -> Any:
    if 'date' == 'int':
        return _as_int(value)
    if 'date' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def visitors_describe_arrives_on() -> str:
    required = 'required' if True else 'optional'
    return 'Arrives On is a ' + required + ' date field on Visitor Desk (visitors).'


def visitors_check_status(value: Any) -> list[str]:
    """Field policy for Status inside Visitor Desk."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Status is required on Visitor Desk.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Status is zero; confirm the Visitor Desk case.')
        if number > 9_000_000_000:
            notes.append('Status exceeds the Visitor Desk ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Status must be YYYY-MM-DD for Visitor Desk.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Status is longer than the Visitor Desk ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Status placeholder values are not allowed on Visitor Desk.')
    return notes


def visitors_normalize_status(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def visitors_describe_status() -> str:
    required = 'required' if True else 'optional'
    return 'Status is a ' + required + ' str field on Visitor Desk (visitors).'


FIELD_CHECKS_VISITORS = {
    'visitor_name': visitors_check_visitor_name,
    'host_name': visitors_check_host_name,
    'company': visitors_check_company,
    'arrives_on': visitors_check_arrives_on,
    'status': visitors_check_status,
}


def visitors_run_field_checks(row: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for name, checker in FIELD_CHECKS_VISITORS.items():
        found.extend(checker(row.get(name)))
    return found


def visitors_policy_card(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'domain': DOMAIN_KEY,
        'title': DOMAIN_TITLE,
        'band': visitors_risk_band(row),
        'owner': visitors_owner_hint(row),
        'sla_hours': visitors_sla_hours(row),
        'exceptions': visitors_exception_needed(row),
        'freeze': visitors_freeze_window(row),
        'violations': policy.collect(row) + visitors_run_field_checks(row),
        'summary': visitors_summary_line(row),
    }

