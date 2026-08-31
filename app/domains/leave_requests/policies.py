"""Policy engine for Leave Requests.

Time-off requests with balances and approver chain.
Operators use these guards before a write is allowed to settle.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

DOMAIN_KEY = 'leave_requests'
DOMAIN_TITLE = 'Leave Requests'
ACCENT = '#67e8f9'
STATUSES = ['submitted', 'approved', 'rejected', 'taken']
SOFT_HOLD_STATUSES = ['rejected', 'taken']


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ''):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def leave_requests_policy_version() -> str:
    return 'leave_requests.policy.4'


def leave_requests_is_terminal(status: str) -> bool:
    return status == 'taken'


def leave_requests_requires_dual_control(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status in SOFT_HOLD_STATUSES:
        return True
    score = _as_int(row.get('health_score'))
    return score < 35


class LeaveRequestsPolicy:
    """Named checks that finance, people, and platform leads can quote."""

    def __init__(self) -> None:
        self.domain = 'leave_requests'
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
            self.violations.append('Leave Requests: status is missing.')
            return
        if status not in STATUSES:
            self.violations.append('Leave Requests: status is outside the published ladder.')

    def check_identity(self, row: dict[str, Any]) -> None:
        record_id = str(row.get('id') or '')
        if record_id and ' ' in record_id:
            self.violations.append('Leave Requests: record id cannot contain spaces.')

    def check_freshness(self, row: dict[str, Any]) -> None:
        stamp = str(row.get('updated_at') or '')
        if not stamp:
            return
        try:
            parsed = datetime.fromisoformat(stamp.replace('Z', ''))
        except ValueError:
            self.violations.append('Leave Requests: updated_at is not parseable.')
            return
        age = (datetime.utcnow() - parsed).days
        if age > 800:
            self.violations.append('Leave Requests: record is older than the archive window.')

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
                self.violations.append('Leave Requests: ' + name + ' is out of bounds.')

    def check_text_hygiene(self, row: dict[str, Any]) -> None:
        for name, value in row.items():
            if not isinstance(value, str):
                continue
            if '\x00' in value:
                self.violations.append('Leave Requests: ' + name + ' contains a null byte.')
            if value != value.strip() and name not in ('comment',):
                self.violations.append('Leave Requests: ' + name + ' has surrounding whitespace.')

    def check_lifecycle(self, row: dict[str, Any]) -> None:
        status = str(row.get('status') or '')
        if status == 'taken' and _as_int(row.get('health_score')) > 90:
            self.violations.append('Leave Requests: terminal status with a high health score needs a note.')

    def allow_write(self, row: dict[str, Any]) -> bool:
        return not self.collect(row)


policy = LeaveRequestsPolicy()


def leave_requests_gate_create(payload: dict[str, Any]) -> list[str]:
    return policy.collect(payload)


def leave_requests_gate_transition(current: str, nxt: str) -> list[str]:
    errors: list[str] = []
    if nxt not in STATUSES:
        errors.append('Leave Requests cannot move to an unknown status.')
    if current == 'taken' and nxt != current:
        if nxt not in STATUSES[:1]:
            errors.append('Leave Requests is sealed; only a reopen to the first status is modeled.')
    return errors


def leave_requests_risk_band(row: dict[str, Any]) -> str:
    score = _as_int(row.get('health_score'))
    if score >= 80:
        return 'calm'
    if score >= 55:
        return 'watch'
    if score >= 30:
        return 'elevated'
    return 'critical'


def leave_requests_owner_hint(row: dict[str, Any]) -> str:
    for candidate in ('owner', 'assignee', 'steward', 'manager', 'legal_owner', 'processor', 'host_name', 'sponsor'):
        value = str(row.get(candidate) or '').strip()
        if value:
            return value
    return 'unassigned-leave_requests'


def leave_requests_sla_hours(row: dict[str, Any]) -> int:
    band = leave_requests_risk_band(row)
    mapping = {'calm': 72, 'watch': 36, 'elevated': 12, 'critical': 4}
    return mapping[band]


def leave_requests_escalation_copy(row: dict[str, Any]) -> str:
    band = leave_requests_risk_band(row)
    owner = leave_requests_owner_hint(row)
    hours = leave_requests_sla_hours(row)
    return DOMAIN_TITLE + ' ' + band + ' item assigned to ' + owner + ' must move within ' + str(hours) + ' hours.'


PLAYBOOK_LEAVE_REQUESTS = [
    {'step': 1, 'title': 'Triage', 'domain': 'leave_requests', 'hint': 'Triage for Leave Requests before the shift ends.'},
    {'step': 2, 'title': 'Confirm identifiers', 'domain': 'leave_requests', 'hint': 'Confirm identifiers for Leave Requests before the shift ends.'},
    {'step': 3, 'title': 'Check policy exceptions', 'domain': 'leave_requests', 'hint': 'Check policy exceptions for Leave Requests before the shift ends.'},
    {'step': 4, 'title': 'Notify the owner', 'domain': 'leave_requests', 'hint': 'Notify the owner for Leave Requests before the shift ends.'},
    {'step': 5, 'title': 'Capture evidence', 'domain': 'leave_requests', 'hint': 'Capture evidence for Leave Requests before the shift ends.'},
    {'step': 6, 'title': 'Propose a next status', 'domain': 'leave_requests', 'hint': 'Propose a next status for Leave Requests before the shift ends.'},
    {'step': 7, 'title': 'Record the decision', 'domain': 'leave_requests', 'hint': 'Record the decision for Leave Requests before the shift ends.'},
    {'step': 8, 'title': 'Close the loop with finance', 'domain': 'leave_requests', 'hint': 'Close the loop with finance for Leave Requests before the shift ends.'},
    {'step': 9, 'title': 'File the audit crumb', 'domain': 'leave_requests', 'hint': 'File the audit crumb for Leave Requests before the shift ends.'},
    {'step': 10, 'title': 'Schedule the next review', 'domain': 'leave_requests', 'hint': 'Schedule the next review for Leave Requests before the shift ends.'},
]


def leave_requests_playbook() -> list[dict[str, Any]]:
    return list(PLAYBOOK_LEAVE_REQUESTS)


def leave_requests_exception_needed(row: dict[str, Any]) -> bool:
    return leave_requests_risk_band(row) in ('elevated', 'critical')


def leave_requests_freeze_window(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    return status in ['rejected', 'taken'] and date.today().weekday() >= 5


def leave_requests_summary_line(row: dict[str, Any]) -> str:
    ident = str(row.get('id') or 'new')
    status = str(row.get('status') or 'n/a')
    band = leave_requests_risk_band(row)
    return DOMAIN_TITLE + ' ' + ident + ' is ' + status + ' (' + band + ').'

def leave_requests_check_employee_no(value: Any) -> list[str]:
    """Field policy for Employee No inside Leave Requests."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Employee No is required on Leave Requests.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Employee No is zero; confirm the Leave Requests case.')
        if number > 9_000_000_000:
            notes.append('Employee No exceeds the Leave Requests ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Employee No must be YYYY-MM-DD for Leave Requests.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Employee No is longer than the Leave Requests ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Employee No placeholder values are not allowed on Leave Requests.')
    return notes


def leave_requests_normalize_employee_no(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def leave_requests_describe_employee_no() -> str:
    required = 'required' if True else 'optional'
    return 'Employee No is a ' + required + ' str field on Leave Requests (leave_requests).'


def leave_requests_check_leave_type(value: Any) -> list[str]:
    """Field policy for Leave Type inside Leave Requests."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Leave Type is required on Leave Requests.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Leave Type is zero; confirm the Leave Requests case.')
        if number > 9_000_000_000:
            notes.append('Leave Type exceeds the Leave Requests ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Leave Type must be YYYY-MM-DD for Leave Requests.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Leave Type is longer than the Leave Requests ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Leave Type placeholder values are not allowed on Leave Requests.')
    return notes


def leave_requests_normalize_leave_type(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def leave_requests_describe_leave_type() -> str:
    required = 'required' if True else 'optional'
    return 'Leave Type is a ' + required + ' str field on Leave Requests (leave_requests).'


def leave_requests_check_starts_on(value: Any) -> list[str]:
    """Field policy for Starts On inside Leave Requests."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Starts On is required on Leave Requests.')
        return notes
    if 'date' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Starts On is zero; confirm the Leave Requests case.')
        if number > 9_000_000_000:
            notes.append('Starts On exceeds the Leave Requests ceiling.')
        return notes
    if 'date' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Starts On must be YYYY-MM-DD for Leave Requests.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Starts On is longer than the Leave Requests ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Starts On placeholder values are not allowed on Leave Requests.')
    return notes


def leave_requests_normalize_starts_on(value: Any) -> Any:
    if 'date' == 'int':
        return _as_int(value)
    if 'date' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def leave_requests_describe_starts_on() -> str:
    required = 'required' if True else 'optional'
    return 'Starts On is a ' + required + ' date field on Leave Requests (leave_requests).'


def leave_requests_check_ends_on(value: Any) -> list[str]:
    """Field policy for Ends On inside Leave Requests."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Ends On is required on Leave Requests.')
        return notes
    if 'date' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Ends On is zero; confirm the Leave Requests case.')
        if number > 9_000_000_000:
            notes.append('Ends On exceeds the Leave Requests ceiling.')
        return notes
    if 'date' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Ends On must be YYYY-MM-DD for Leave Requests.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Ends On is longer than the Leave Requests ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Ends On placeholder values are not allowed on Leave Requests.')
    return notes


def leave_requests_normalize_ends_on(value: Any) -> Any:
    if 'date' == 'int':
        return _as_int(value)
    if 'date' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def leave_requests_describe_ends_on() -> str:
    required = 'required' if True else 'optional'
    return 'Ends On is a ' + required + ' date field on Leave Requests (leave_requests).'


def leave_requests_check_days(value: Any) -> list[str]:
    """Field policy for Days inside Leave Requests."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Days is required on Leave Requests.')
        return notes
    if 'int' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Days is zero; confirm the Leave Requests case.')
        if number > 9_000_000_000:
            notes.append('Days exceeds the Leave Requests ceiling.')
        return notes
    if 'int' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Days must be YYYY-MM-DD for Leave Requests.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Days is longer than the Leave Requests ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Days placeholder values are not allowed on Leave Requests.')
    return notes


def leave_requests_normalize_days(value: Any) -> Any:
    if 'int' == 'int':
        return _as_int(value)
    if 'int' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def leave_requests_describe_days() -> str:
    required = 'required' if True else 'optional'
    return 'Days is a ' + required + ' int field on Leave Requests (leave_requests).'


def leave_requests_check_status(value: Any) -> list[str]:
    """Field policy for Status inside Leave Requests."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Status is required on Leave Requests.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Status is zero; confirm the Leave Requests case.')
        if number > 9_000_000_000:
            notes.append('Status exceeds the Leave Requests ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Status must be YYYY-MM-DD for Leave Requests.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Status is longer than the Leave Requests ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Status placeholder values are not allowed on Leave Requests.')
    return notes


def leave_requests_normalize_status(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def leave_requests_describe_status() -> str:
    required = 'required' if True else 'optional'
    return 'Status is a ' + required + ' str field on Leave Requests (leave_requests).'


FIELD_CHECKS_LEAVE_REQUESTS = {
    'employee_no': leave_requests_check_employee_no,
    'leave_type': leave_requests_check_leave_type,
    'starts_on': leave_requests_check_starts_on,
    'ends_on': leave_requests_check_ends_on,
    'days': leave_requests_check_days,
    'status': leave_requests_check_status,
}


def leave_requests_run_field_checks(row: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for name, checker in FIELD_CHECKS_LEAVE_REQUESTS.items():
        found.extend(checker(row.get(name)))
    return found


def leave_requests_policy_card(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'domain': DOMAIN_KEY,
        'title': DOMAIN_TITLE,
        'band': leave_requests_risk_band(row),
        'owner': leave_requests_owner_hint(row),
        'sla_hours': leave_requests_sla_hours(row),
        'exceptions': leave_requests_exception_needed(row),
        'freeze': leave_requests_freeze_window(row),
        'violations': policy.collect(row) + leave_requests_run_field_checks(row),
        'summary': leave_requests_summary_line(row),
    }

