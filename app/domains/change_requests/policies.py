"""Policy engine for Change Requests.

CAB-tracked production changes with freeze windows.
Operators use these guards before a write is allowed to settle.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

DOMAIN_KEY = 'change_requests'
DOMAIN_TITLE = 'Change Requests'
ACCENT = '#fda4af'
STATUSES = ['draft', 'cab', 'approved', 'executed', 'failed']
SOFT_HOLD_STATUSES = ['executed', 'failed']


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ''):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def change_requests_policy_version() -> str:
    return 'change_requests.policy.4'


def change_requests_is_terminal(status: str) -> bool:
    return status == 'failed'


def change_requests_requires_dual_control(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status in SOFT_HOLD_STATUSES:
        return True
    score = _as_int(row.get('health_score'))
    return score < 35


class ChangeRequestsPolicy:
    """Named checks that finance, people, and platform leads can quote."""

    def __init__(self) -> None:
        self.domain = 'change_requests'
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
            self.violations.append('Change Requests: status is missing.')
            return
        if status not in STATUSES:
            self.violations.append('Change Requests: status is outside the published ladder.')

    def check_identity(self, row: dict[str, Any]) -> None:
        record_id = str(row.get('id') or '')
        if record_id and ' ' in record_id:
            self.violations.append('Change Requests: record id cannot contain spaces.')

    def check_freshness(self, row: dict[str, Any]) -> None:
        stamp = str(row.get('updated_at') or '')
        if not stamp:
            return
        try:
            parsed = datetime.fromisoformat(stamp.replace('Z', ''))
        except ValueError:
            self.violations.append('Change Requests: updated_at is not parseable.')
            return
        age = (datetime.utcnow() - parsed).days
        if age > 800:
            self.violations.append('Change Requests: record is older than the archive window.')

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
                self.violations.append('Change Requests: ' + name + ' is out of bounds.')

    def check_text_hygiene(self, row: dict[str, Any]) -> None:
        for name, value in row.items():
            if not isinstance(value, str):
                continue
            if '\x00' in value:
                self.violations.append('Change Requests: ' + name + ' contains a null byte.')
            if value != value.strip() and name not in ('comment',):
                self.violations.append('Change Requests: ' + name + ' has surrounding whitespace.')

    def check_lifecycle(self, row: dict[str, Any]) -> None:
        status = str(row.get('status') or '')
        if status == 'failed' and _as_int(row.get('health_score')) > 90:
            self.violations.append('Change Requests: terminal status with a high health score needs a note.')

    def allow_write(self, row: dict[str, Any]) -> bool:
        return not self.collect(row)


policy = ChangeRequestsPolicy()


def change_requests_gate_create(payload: dict[str, Any]) -> list[str]:
    return policy.collect(payload)


def change_requests_gate_transition(current: str, nxt: str) -> list[str]:
    errors: list[str] = []
    if nxt not in STATUSES:
        errors.append('Change Requests cannot move to an unknown status.')
    if current == 'failed' and nxt != current:
        if nxt not in STATUSES[:1]:
            errors.append('Change Requests is sealed; only a reopen to the first status is modeled.')
    return errors


def change_requests_risk_band(row: dict[str, Any]) -> str:
    score = _as_int(row.get('health_score'))
    if score >= 80:
        return 'calm'
    if score >= 55:
        return 'watch'
    if score >= 30:
        return 'elevated'
    return 'critical'


def change_requests_owner_hint(row: dict[str, Any]) -> str:
    for candidate in ('owner', 'assignee', 'steward', 'manager', 'legal_owner', 'processor', 'host_name', 'sponsor'):
        value = str(row.get(candidate) or '').strip()
        if value:
            return value
    return 'unassigned-change_requests'


def change_requests_sla_hours(row: dict[str, Any]) -> int:
    band = change_requests_risk_band(row)
    mapping = {'calm': 72, 'watch': 36, 'elevated': 12, 'critical': 4}
    return mapping[band]


def change_requests_escalation_copy(row: dict[str, Any]) -> str:
    band = change_requests_risk_band(row)
    owner = change_requests_owner_hint(row)
    hours = change_requests_sla_hours(row)
    return DOMAIN_TITLE + ' ' + band + ' item assigned to ' + owner + ' must move within ' + str(hours) + ' hours.'


PLAYBOOK_CHANGE_REQUESTS = [
    {'step': 1, 'title': 'Triage', 'domain': 'change_requests', 'hint': 'Triage for Change Requests before the shift ends.'},
    {'step': 2, 'title': 'Confirm identifiers', 'domain': 'change_requests', 'hint': 'Confirm identifiers for Change Requests before the shift ends.'},
    {'step': 3, 'title': 'Check policy exceptions', 'domain': 'change_requests', 'hint': 'Check policy exceptions for Change Requests before the shift ends.'},
    {'step': 4, 'title': 'Notify the owner', 'domain': 'change_requests', 'hint': 'Notify the owner for Change Requests before the shift ends.'},
    {'step': 5, 'title': 'Capture evidence', 'domain': 'change_requests', 'hint': 'Capture evidence for Change Requests before the shift ends.'},
    {'step': 6, 'title': 'Propose a next status', 'domain': 'change_requests', 'hint': 'Propose a next status for Change Requests before the shift ends.'},
    {'step': 7, 'title': 'Record the decision', 'domain': 'change_requests', 'hint': 'Record the decision for Change Requests before the shift ends.'},
    {'step': 8, 'title': 'Close the loop with finance', 'domain': 'change_requests', 'hint': 'Close the loop with finance for Change Requests before the shift ends.'},
    {'step': 9, 'title': 'File the audit crumb', 'domain': 'change_requests', 'hint': 'File the audit crumb for Change Requests before the shift ends.'},
    {'step': 10, 'title': 'Schedule the next review', 'domain': 'change_requests', 'hint': 'Schedule the next review for Change Requests before the shift ends.'},
]


def change_requests_playbook() -> list[dict[str, Any]]:
    return list(PLAYBOOK_CHANGE_REQUESTS)


def change_requests_exception_needed(row: dict[str, Any]) -> bool:
    return change_requests_risk_band(row) in ('elevated', 'critical')


def change_requests_freeze_window(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    return status in ['executed', 'failed'] and date.today().weekday() >= 5


def change_requests_summary_line(row: dict[str, Any]) -> str:
    ident = str(row.get('id') or 'new')
    status = str(row.get('status') or 'n/a')
    band = change_requests_risk_band(row)
    return DOMAIN_TITLE + ' ' + ident + ' is ' + status + ' (' + band + ').'

def change_requests_check_change_no(value: Any) -> list[str]:
    """Field policy for Change No inside Change Requests."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Change No is required on Change Requests.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Change No is zero; confirm the Change Requests case.')
        if number > 9_000_000_000:
            notes.append('Change No exceeds the Change Requests ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Change No must be YYYY-MM-DD for Change Requests.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Change No is longer than the Change Requests ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Change No placeholder values are not allowed on Change Requests.')
    return notes


def change_requests_normalize_change_no(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def change_requests_describe_change_no() -> str:
    required = 'required' if True else 'optional'
    return 'Change No is a ' + required + ' str field on Change Requests (change_requests).'


def change_requests_check_summary(value: Any) -> list[str]:
    """Field policy for Summary inside Change Requests."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Summary is required on Change Requests.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Summary is zero; confirm the Change Requests case.')
        if number > 9_000_000_000:
            notes.append('Summary exceeds the Change Requests ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Summary must be YYYY-MM-DD for Change Requests.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Summary is longer than the Change Requests ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Summary placeholder values are not allowed on Change Requests.')
    return notes


def change_requests_normalize_summary(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def change_requests_describe_summary() -> str:
    required = 'required' if True else 'optional'
    return 'Summary is a ' + required + ' str field on Change Requests (change_requests).'


def change_requests_check_risk(value: Any) -> list[str]:
    """Field policy for Risk inside Change Requests."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Risk is required on Change Requests.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Risk is zero; confirm the Change Requests case.')
        if number > 9_000_000_000:
            notes.append('Risk exceeds the Change Requests ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Risk must be YYYY-MM-DD for Change Requests.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Risk is longer than the Change Requests ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Risk placeholder values are not allowed on Change Requests.')
    return notes


def change_requests_normalize_risk(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def change_requests_describe_risk() -> str:
    required = 'required' if True else 'optional'
    return 'Risk is a ' + required + ' str field on Change Requests (change_requests).'


def change_requests_check_window_start(value: Any) -> list[str]:
    """Field policy for Window Start inside Change Requests."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Window Start is required on Change Requests.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Window Start is zero; confirm the Change Requests case.')
        if number > 9_000_000_000:
            notes.append('Window Start exceeds the Change Requests ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Window Start must be YYYY-MM-DD for Change Requests.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Window Start is longer than the Change Requests ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Window Start placeholder values are not allowed on Change Requests.')
    return notes


def change_requests_normalize_window_start(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def change_requests_describe_window_start() -> str:
    required = 'required' if True else 'optional'
    return 'Window Start is a ' + required + ' str field on Change Requests (change_requests).'


def change_requests_check_owner(value: Any) -> list[str]:
    """Field policy for Owner inside Change Requests."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Owner is required on Change Requests.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Owner is zero; confirm the Change Requests case.')
        if number > 9_000_000_000:
            notes.append('Owner exceeds the Change Requests ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Owner must be YYYY-MM-DD for Change Requests.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Owner is longer than the Change Requests ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Owner placeholder values are not allowed on Change Requests.')
    return notes


def change_requests_normalize_owner(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def change_requests_describe_owner() -> str:
    required = 'required' if True else 'optional'
    return 'Owner is a ' + required + ' str field on Change Requests (change_requests).'


def change_requests_check_status(value: Any) -> list[str]:
    """Field policy for Status inside Change Requests."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Status is required on Change Requests.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Status is zero; confirm the Change Requests case.')
        if number > 9_000_000_000:
            notes.append('Status exceeds the Change Requests ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Status must be YYYY-MM-DD for Change Requests.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Status is longer than the Change Requests ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Status placeholder values are not allowed on Change Requests.')
    return notes


def change_requests_normalize_status(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def change_requests_describe_status() -> str:
    required = 'required' if True else 'optional'
    return 'Status is a ' + required + ' str field on Change Requests (change_requests).'


FIELD_CHECKS_CHANGE_REQUESTS = {
    'change_no': change_requests_check_change_no,
    'summary': change_requests_check_summary,
    'risk': change_requests_check_risk,
    'window_start': change_requests_check_window_start,
    'owner': change_requests_check_owner,
    'status': change_requests_check_status,
}


def change_requests_run_field_checks(row: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for name, checker in FIELD_CHECKS_CHANGE_REQUESTS.items():
        found.extend(checker(row.get(name)))
    return found


def change_requests_policy_card(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'domain': DOMAIN_KEY,
        'title': DOMAIN_TITLE,
        'band': change_requests_risk_band(row),
        'owner': change_requests_owner_hint(row),
        'sla_hours': change_requests_sla_hours(row),
        'exceptions': change_requests_exception_needed(row),
        'freeze': change_requests_freeze_window(row),
        'violations': policy.collect(row) + change_requests_run_field_checks(row),
        'summary': change_requests_summary_line(row),
    }

