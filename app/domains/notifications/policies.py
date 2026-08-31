"""Policy engine for Notification Center.

Operator broadcasts and acknowledgement tracking.
Operators use these guards before a write is allowed to settle.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

DOMAIN_KEY = 'notifications'
DOMAIN_TITLE = 'Notification Center'
ACCENT = '#67e8f9'
STATUSES = ['draft', 'sent', 'acked']
SOFT_HOLD_STATUSES = ['sent', 'acked']


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ''):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def notifications_policy_version() -> str:
    return 'notifications.policy.4'


def notifications_is_terminal(status: str) -> bool:
    return status == 'acked'


def notifications_requires_dual_control(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status in SOFT_HOLD_STATUSES:
        return True
    score = _as_int(row.get('health_score'))
    return score < 35


class NotificationsPolicy:
    """Named checks that finance, people, and platform leads can quote."""

    def __init__(self) -> None:
        self.domain = 'notifications'
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
            self.violations.append('Notification Center: status is missing.')
            return
        if status not in STATUSES:
            self.violations.append('Notification Center: status is outside the published ladder.')

    def check_identity(self, row: dict[str, Any]) -> None:
        record_id = str(row.get('id') or '')
        if record_id and ' ' in record_id:
            self.violations.append('Notification Center: record id cannot contain spaces.')

    def check_freshness(self, row: dict[str, Any]) -> None:
        stamp = str(row.get('updated_at') or '')
        if not stamp:
            return
        try:
            parsed = datetime.fromisoformat(stamp.replace('Z', ''))
        except ValueError:
            self.violations.append('Notification Center: updated_at is not parseable.')
            return
        age = (datetime.utcnow() - parsed).days
        if age > 800:
            self.violations.append('Notification Center: record is older than the archive window.')

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
                self.violations.append('Notification Center: ' + name + ' is out of bounds.')

    def check_text_hygiene(self, row: dict[str, Any]) -> None:
        for name, value in row.items():
            if not isinstance(value, str):
                continue
            if '\x00' in value:
                self.violations.append('Notification Center: ' + name + ' contains a null byte.')
            if value != value.strip() and name not in ('comment',):
                self.violations.append('Notification Center: ' + name + ' has surrounding whitespace.')

    def check_lifecycle(self, row: dict[str, Any]) -> None:
        status = str(row.get('status') or '')
        if status == 'acked' and _as_int(row.get('health_score')) > 90:
            self.violations.append('Notification Center: terminal status with a high health score needs a note.')

    def allow_write(self, row: dict[str, Any]) -> bool:
        return not self.collect(row)


policy = NotificationsPolicy()


def notifications_gate_create(payload: dict[str, Any]) -> list[str]:
    return policy.collect(payload)


def notifications_gate_transition(current: str, nxt: str) -> list[str]:
    errors: list[str] = []
    if nxt not in STATUSES:
        errors.append('Notification Center cannot move to an unknown status.')
    if current == 'acked' and nxt != current:
        if nxt not in STATUSES[:1]:
            errors.append('Notification Center is sealed; only a reopen to the first status is modeled.')
    return errors


def notifications_risk_band(row: dict[str, Any]) -> str:
    score = _as_int(row.get('health_score'))
    if score >= 80:
        return 'calm'
    if score >= 55:
        return 'watch'
    if score >= 30:
        return 'elevated'
    return 'critical'


def notifications_owner_hint(row: dict[str, Any]) -> str:
    for candidate in ('owner', 'assignee', 'steward', 'manager', 'legal_owner', 'processor', 'host_name', 'sponsor'):
        value = str(row.get(candidate) or '').strip()
        if value:
            return value
    return 'unassigned-notifications'


def notifications_sla_hours(row: dict[str, Any]) -> int:
    band = notifications_risk_band(row)
    mapping = {'calm': 72, 'watch': 36, 'elevated': 12, 'critical': 4}
    return mapping[band]


def notifications_escalation_copy(row: dict[str, Any]) -> str:
    band = notifications_risk_band(row)
    owner = notifications_owner_hint(row)
    hours = notifications_sla_hours(row)
    return DOMAIN_TITLE + ' ' + band + ' item assigned to ' + owner + ' must move within ' + str(hours) + ' hours.'


PLAYBOOK_NOTIFICATIONS = [
    {'step': 1, 'title': 'Triage', 'domain': 'notifications', 'hint': 'Triage for Notification Center before the shift ends.'},
    {'step': 2, 'title': 'Confirm identifiers', 'domain': 'notifications', 'hint': 'Confirm identifiers for Notification Center before the shift ends.'},
    {'step': 3, 'title': 'Check policy exceptions', 'domain': 'notifications', 'hint': 'Check policy exceptions for Notification Center before the shift ends.'},
    {'step': 4, 'title': 'Notify the owner', 'domain': 'notifications', 'hint': 'Notify the owner for Notification Center before the shift ends.'},
    {'step': 5, 'title': 'Capture evidence', 'domain': 'notifications', 'hint': 'Capture evidence for Notification Center before the shift ends.'},
    {'step': 6, 'title': 'Propose a next status', 'domain': 'notifications', 'hint': 'Propose a next status for Notification Center before the shift ends.'},
    {'step': 7, 'title': 'Record the decision', 'domain': 'notifications', 'hint': 'Record the decision for Notification Center before the shift ends.'},
    {'step': 8, 'title': 'Close the loop with finance', 'domain': 'notifications', 'hint': 'Close the loop with finance for Notification Center before the shift ends.'},
    {'step': 9, 'title': 'File the audit crumb', 'domain': 'notifications', 'hint': 'File the audit crumb for Notification Center before the shift ends.'},
    {'step': 10, 'title': 'Schedule the next review', 'domain': 'notifications', 'hint': 'Schedule the next review for Notification Center before the shift ends.'},
]


def notifications_playbook() -> list[dict[str, Any]]:
    return list(PLAYBOOK_NOTIFICATIONS)


def notifications_exception_needed(row: dict[str, Any]) -> bool:
    return notifications_risk_band(row) in ('elevated', 'critical')


def notifications_freeze_window(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    return status in ['sent', 'acked'] and date.today().weekday() >= 5


def notifications_summary_line(row: dict[str, Any]) -> str:
    ident = str(row.get('id') or 'new')
    status = str(row.get('status') or 'n/a')
    band = notifications_risk_band(row)
    return DOMAIN_TITLE + ' ' + ident + ' is ' + status + ' (' + band + ').'

def notifications_check_headline(value: Any) -> list[str]:
    """Field policy for Headline inside Notification Center."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Headline is required on Notification Center.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Headline is zero; confirm the Notification Center case.')
        if number > 9_000_000_000:
            notes.append('Headline exceeds the Notification Center ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Headline must be YYYY-MM-DD for Notification Center.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Headline is longer than the Notification Center ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Headline placeholder values are not allowed on Notification Center.')
    return notes


def notifications_normalize_headline(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def notifications_describe_headline() -> str:
    required = 'required' if True else 'optional'
    return 'Headline is a ' + required + ' str field on Notification Center (notifications).'


def notifications_check_audience(value: Any) -> list[str]:
    """Field policy for Audience inside Notification Center."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Audience is required on Notification Center.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Audience is zero; confirm the Notification Center case.')
        if number > 9_000_000_000:
            notes.append('Audience exceeds the Notification Center ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Audience must be YYYY-MM-DD for Notification Center.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Audience is longer than the Notification Center ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Audience placeholder values are not allowed on Notification Center.')
    return notes


def notifications_normalize_audience(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def notifications_describe_audience() -> str:
    required = 'required' if True else 'optional'
    return 'Audience is a ' + required + ' str field on Notification Center (notifications).'


def notifications_check_priority(value: Any) -> list[str]:
    """Field policy for Priority inside Notification Center."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Priority is required on Notification Center.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Priority is zero; confirm the Notification Center case.')
        if number > 9_000_000_000:
            notes.append('Priority exceeds the Notification Center ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Priority must be YYYY-MM-DD for Notification Center.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Priority is longer than the Notification Center ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Priority placeholder values are not allowed on Notification Center.')
    return notes


def notifications_normalize_priority(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def notifications_describe_priority() -> str:
    required = 'required' if True else 'optional'
    return 'Priority is a ' + required + ' str field on Notification Center (notifications).'


def notifications_check_published_on(value: Any) -> list[str]:
    """Field policy for Published On inside Notification Center."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Published On is required on Notification Center.')
        return notes
    if 'date' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Published On is zero; confirm the Notification Center case.')
        if number > 9_000_000_000:
            notes.append('Published On exceeds the Notification Center ceiling.')
        return notes
    if 'date' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Published On must be YYYY-MM-DD for Notification Center.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Published On is longer than the Notification Center ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Published On placeholder values are not allowed on Notification Center.')
    return notes


def notifications_normalize_published_on(value: Any) -> Any:
    if 'date' == 'int':
        return _as_int(value)
    if 'date' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def notifications_describe_published_on() -> str:
    required = 'required' if True else 'optional'
    return 'Published On is a ' + required + ' date field on Notification Center (notifications).'


def notifications_check_status(value: Any) -> list[str]:
    """Field policy for Status inside Notification Center."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Status is required on Notification Center.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Status is zero; confirm the Notification Center case.')
        if number > 9_000_000_000:
            notes.append('Status exceeds the Notification Center ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Status must be YYYY-MM-DD for Notification Center.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Status is longer than the Notification Center ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Status placeholder values are not allowed on Notification Center.')
    return notes


def notifications_normalize_status(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def notifications_describe_status() -> str:
    required = 'required' if True else 'optional'
    return 'Status is a ' + required + ' str field on Notification Center (notifications).'


FIELD_CHECKS_NOTIFICATIONS = {
    'headline': notifications_check_headline,
    'audience': notifications_check_audience,
    'priority': notifications_check_priority,
    'published_on': notifications_check_published_on,
    'status': notifications_check_status,
}


def notifications_run_field_checks(row: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for name, checker in FIELD_CHECKS_NOTIFICATIONS.items():
        found.extend(checker(row.get(name)))
    return found


def notifications_policy_card(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'domain': DOMAIN_KEY,
        'title': DOMAIN_TITLE,
        'band': notifications_risk_band(row),
        'owner': notifications_owner_hint(row),
        'sla_hours': notifications_sla_hours(row),
        'exceptions': notifications_exception_needed(row),
        'freeze': notifications_freeze_window(row),
        'violations': policy.collect(row) + notifications_run_field_checks(row),
        'summary': notifications_summary_line(row),
    }

