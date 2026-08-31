"""Policy engine for Postmortems.

Incident write-ups with action items and due dates.
Operators use these guards before a write is allowed to settle.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

DOMAIN_KEY = 'postmortems'
DOMAIN_TITLE = 'Postmortems'
ACCENT = '#fda4af'
STATUSES = ['writing', 'review', 'published']
SOFT_HOLD_STATUSES = ['review', 'published']


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ''):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def postmortems_policy_version() -> str:
    return 'postmortems.policy.4'


def postmortems_is_terminal(status: str) -> bool:
    return status == 'published'


def postmortems_requires_dual_control(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status in SOFT_HOLD_STATUSES:
        return True
    score = _as_int(row.get('health_score'))
    return score < 35


class PostmortemsPolicy:
    """Named checks that finance, people, and platform leads can quote."""

    def __init__(self) -> None:
        self.domain = 'postmortems'
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
            self.violations.append('Postmortems: status is missing.')
            return
        if status not in STATUSES:
            self.violations.append('Postmortems: status is outside the published ladder.')

    def check_identity(self, row: dict[str, Any]) -> None:
        record_id = str(row.get('id') or '')
        if record_id and ' ' in record_id:
            self.violations.append('Postmortems: record id cannot contain spaces.')

    def check_freshness(self, row: dict[str, Any]) -> None:
        stamp = str(row.get('updated_at') or '')
        if not stamp:
            return
        try:
            parsed = datetime.fromisoformat(stamp.replace('Z', ''))
        except ValueError:
            self.violations.append('Postmortems: updated_at is not parseable.')
            return
        age = (datetime.utcnow() - parsed).days
        if age > 800:
            self.violations.append('Postmortems: record is older than the archive window.')

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
                self.violations.append('Postmortems: ' + name + ' is out of bounds.')

    def check_text_hygiene(self, row: dict[str, Any]) -> None:
        for name, value in row.items():
            if not isinstance(value, str):
                continue
            if '\x00' in value:
                self.violations.append('Postmortems: ' + name + ' contains a null byte.')
            if value != value.strip() and name not in ('comment',):
                self.violations.append('Postmortems: ' + name + ' has surrounding whitespace.')

    def check_lifecycle(self, row: dict[str, Any]) -> None:
        status = str(row.get('status') or '')
        if status == 'published' and _as_int(row.get('health_score')) > 90:
            self.violations.append('Postmortems: terminal status with a high health score needs a note.')

    def allow_write(self, row: dict[str, Any]) -> bool:
        return not self.collect(row)


policy = PostmortemsPolicy()


def postmortems_gate_create(payload: dict[str, Any]) -> list[str]:
    return policy.collect(payload)


def postmortems_gate_transition(current: str, nxt: str) -> list[str]:
    errors: list[str] = []
    if nxt not in STATUSES:
        errors.append('Postmortems cannot move to an unknown status.')
    if current == 'published' and nxt != current:
        if nxt not in STATUSES[:1]:
            errors.append('Postmortems is sealed; only a reopen to the first status is modeled.')
    return errors


def postmortems_risk_band(row: dict[str, Any]) -> str:
    score = _as_int(row.get('health_score'))
    if score >= 80:
        return 'calm'
    if score >= 55:
        return 'watch'
    if score >= 30:
        return 'elevated'
    return 'critical'


def postmortems_owner_hint(row: dict[str, Any]) -> str:
    for candidate in ('owner', 'assignee', 'steward', 'manager', 'legal_owner', 'processor', 'host_name', 'sponsor'):
        value = str(row.get(candidate) or '').strip()
        if value:
            return value
    return 'unassigned-postmortems'


def postmortems_sla_hours(row: dict[str, Any]) -> int:
    band = postmortems_risk_band(row)
    mapping = {'calm': 72, 'watch': 36, 'elevated': 12, 'critical': 4}
    return mapping[band]


def postmortems_escalation_copy(row: dict[str, Any]) -> str:
    band = postmortems_risk_band(row)
    owner = postmortems_owner_hint(row)
    hours = postmortems_sla_hours(row)
    return DOMAIN_TITLE + ' ' + band + ' item assigned to ' + owner + ' must move within ' + str(hours) + ' hours.'


PLAYBOOK_POSTMORTEMS = [
    {'step': 1, 'title': 'Triage', 'domain': 'postmortems', 'hint': 'Triage for Postmortems before the shift ends.'},
    {'step': 2, 'title': 'Confirm identifiers', 'domain': 'postmortems', 'hint': 'Confirm identifiers for Postmortems before the shift ends.'},
    {'step': 3, 'title': 'Check policy exceptions', 'domain': 'postmortems', 'hint': 'Check policy exceptions for Postmortems before the shift ends.'},
    {'step': 4, 'title': 'Notify the owner', 'domain': 'postmortems', 'hint': 'Notify the owner for Postmortems before the shift ends.'},
    {'step': 5, 'title': 'Capture evidence', 'domain': 'postmortems', 'hint': 'Capture evidence for Postmortems before the shift ends.'},
    {'step': 6, 'title': 'Propose a next status', 'domain': 'postmortems', 'hint': 'Propose a next status for Postmortems before the shift ends.'},
    {'step': 7, 'title': 'Record the decision', 'domain': 'postmortems', 'hint': 'Record the decision for Postmortems before the shift ends.'},
    {'step': 8, 'title': 'Close the loop with finance', 'domain': 'postmortems', 'hint': 'Close the loop with finance for Postmortems before the shift ends.'},
    {'step': 9, 'title': 'File the audit crumb', 'domain': 'postmortems', 'hint': 'File the audit crumb for Postmortems before the shift ends.'},
    {'step': 10, 'title': 'Schedule the next review', 'domain': 'postmortems', 'hint': 'Schedule the next review for Postmortems before the shift ends.'},
]


def postmortems_playbook() -> list[dict[str, Any]]:
    return list(PLAYBOOK_POSTMORTEMS)


def postmortems_exception_needed(row: dict[str, Any]) -> bool:
    return postmortems_risk_band(row) in ('elevated', 'critical')


def postmortems_freeze_window(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    return status in ['review', 'published'] and date.today().weekday() >= 5


def postmortems_summary_line(row: dict[str, Any]) -> str:
    ident = str(row.get('id') or 'new')
    status = str(row.get('status') or 'n/a')
    band = postmortems_risk_band(row)
    return DOMAIN_TITLE + ' ' + ident + ' is ' + status + ' (' + band + ').'

def postmortems_check_doc_no(value: Any) -> list[str]:
    """Field policy for Doc No inside Postmortems."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Doc No is required on Postmortems.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Doc No is zero; confirm the Postmortems case.')
        if number > 9_000_000_000:
            notes.append('Doc No exceeds the Postmortems ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Doc No must be YYYY-MM-DD for Postmortems.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Doc No is longer than the Postmortems ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Doc No placeholder values are not allowed on Postmortems.')
    return notes


def postmortems_normalize_doc_no(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def postmortems_describe_doc_no() -> str:
    required = 'required' if True else 'optional'
    return 'Doc No is a ' + required + ' str field on Postmortems (postmortems).'


def postmortems_check_incident_no(value: Any) -> list[str]:
    """Field policy for Incident No inside Postmortems."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Incident No is required on Postmortems.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Incident No is zero; confirm the Postmortems case.')
        if number > 9_000_000_000:
            notes.append('Incident No exceeds the Postmortems ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Incident No must be YYYY-MM-DD for Postmortems.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Incident No is longer than the Postmortems ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Incident No placeholder values are not allowed on Postmortems.')
    return notes


def postmortems_normalize_incident_no(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def postmortems_describe_incident_no() -> str:
    required = 'required' if True else 'optional'
    return 'Incident No is a ' + required + ' str field on Postmortems (postmortems).'


def postmortems_check_severity(value: Any) -> list[str]:
    """Field policy for Severity inside Postmortems."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Severity is required on Postmortems.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Severity is zero; confirm the Postmortems case.')
        if number > 9_000_000_000:
            notes.append('Severity exceeds the Postmortems ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Severity must be YYYY-MM-DD for Postmortems.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Severity is longer than the Postmortems ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Severity placeholder values are not allowed on Postmortems.')
    return notes


def postmortems_normalize_severity(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def postmortems_describe_severity() -> str:
    required = 'required' if True else 'optional'
    return 'Severity is a ' + required + ' str field on Postmortems (postmortems).'


def postmortems_check_due_on(value: Any) -> list[str]:
    """Field policy for Due On inside Postmortems."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Due On is required on Postmortems.')
        return notes
    if 'date' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Due On is zero; confirm the Postmortems case.')
        if number > 9_000_000_000:
            notes.append('Due On exceeds the Postmortems ceiling.')
        return notes
    if 'date' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Due On must be YYYY-MM-DD for Postmortems.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Due On is longer than the Postmortems ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Due On placeholder values are not allowed on Postmortems.')
    return notes


def postmortems_normalize_due_on(value: Any) -> Any:
    if 'date' == 'int':
        return _as_int(value)
    if 'date' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def postmortems_describe_due_on() -> str:
    required = 'required' if True else 'optional'
    return 'Due On is a ' + required + ' date field on Postmortems (postmortems).'


def postmortems_check_status(value: Any) -> list[str]:
    """Field policy for Status inside Postmortems."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Status is required on Postmortems.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Status is zero; confirm the Postmortems case.')
        if number > 9_000_000_000:
            notes.append('Status exceeds the Postmortems ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Status must be YYYY-MM-DD for Postmortems.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Status is longer than the Postmortems ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Status placeholder values are not allowed on Postmortems.')
    return notes


def postmortems_normalize_status(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def postmortems_describe_status() -> str:
    required = 'required' if True else 'optional'
    return 'Status is a ' + required + ' str field on Postmortems (postmortems).'


FIELD_CHECKS_POSTMORTEMS = {
    'doc_no': postmortems_check_doc_no,
    'incident_no': postmortems_check_incident_no,
    'severity': postmortems_check_severity,
    'due_on': postmortems_check_due_on,
    'status': postmortems_check_status,
}


def postmortems_run_field_checks(row: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for name, checker in FIELD_CHECKS_POSTMORTEMS.items():
        found.extend(checker(row.get(name)))
    return found


def postmortems_policy_card(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'domain': DOMAIN_KEY,
        'title': DOMAIN_TITLE,
        'band': postmortems_risk_band(row),
        'owner': postmortems_owner_hint(row),
        'sla_hours': postmortems_sla_hours(row),
        'exceptions': postmortems_exception_needed(row),
        'freeze': postmortems_freeze_window(row),
        'violations': policy.collect(row) + postmortems_run_field_checks(row),
        'summary': postmortems_summary_line(row),
    }

