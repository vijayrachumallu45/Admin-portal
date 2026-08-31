"""Policy engine for Webinar Desk.

Demand events with registration caps and host assignments.
Operators use these guards before a write is allowed to settle.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

DOMAIN_KEY = 'webinars'
DOMAIN_TITLE = 'Webinar Desk'
ACCENT = '#e879f9'
STATUSES = ['planned', 'live', 'complete', 'cancelled']
SOFT_HOLD_STATUSES = ['complete', 'cancelled']


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ''):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def webinars_policy_version() -> str:
    return 'webinars.policy.4'


def webinars_is_terminal(status: str) -> bool:
    return status == 'cancelled'


def webinars_requires_dual_control(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status in SOFT_HOLD_STATUSES:
        return True
    score = _as_int(row.get('health_score'))
    return score < 35


class WebinarsPolicy:
    """Named checks that finance, people, and platform leads can quote."""

    def __init__(self) -> None:
        self.domain = 'webinars'
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
            self.violations.append('Webinar Desk: status is missing.')
            return
        if status not in STATUSES:
            self.violations.append('Webinar Desk: status is outside the published ladder.')

    def check_identity(self, row: dict[str, Any]) -> None:
        record_id = str(row.get('id') or '')
        if record_id and ' ' in record_id:
            self.violations.append('Webinar Desk: record id cannot contain spaces.')

    def check_freshness(self, row: dict[str, Any]) -> None:
        stamp = str(row.get('updated_at') or '')
        if not stamp:
            return
        try:
            parsed = datetime.fromisoformat(stamp.replace('Z', ''))
        except ValueError:
            self.violations.append('Webinar Desk: updated_at is not parseable.')
            return
        age = (datetime.utcnow() - parsed).days
        if age > 800:
            self.violations.append('Webinar Desk: record is older than the archive window.')

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
                self.violations.append('Webinar Desk: ' + name + ' is out of bounds.')

    def check_text_hygiene(self, row: dict[str, Any]) -> None:
        for name, value in row.items():
            if not isinstance(value, str):
                continue
            if '\x00' in value:
                self.violations.append('Webinar Desk: ' + name + ' contains a null byte.')
            if value != value.strip() and name not in ('comment',):
                self.violations.append('Webinar Desk: ' + name + ' has surrounding whitespace.')

    def check_lifecycle(self, row: dict[str, Any]) -> None:
        status = str(row.get('status') or '')
        if status == 'cancelled' and _as_int(row.get('health_score')) > 90:
            self.violations.append('Webinar Desk: terminal status with a high health score needs a note.')

    def allow_write(self, row: dict[str, Any]) -> bool:
        return not self.collect(row)


policy = WebinarsPolicy()


def webinars_gate_create(payload: dict[str, Any]) -> list[str]:
    return policy.collect(payload)


def webinars_gate_transition(current: str, nxt: str) -> list[str]:
    errors: list[str] = []
    if nxt not in STATUSES:
        errors.append('Webinar Desk cannot move to an unknown status.')
    if current == 'cancelled' and nxt != current:
        if nxt not in STATUSES[:1]:
            errors.append('Webinar Desk is sealed; only a reopen to the first status is modeled.')
    return errors


def webinars_risk_band(row: dict[str, Any]) -> str:
    score = _as_int(row.get('health_score'))
    if score >= 80:
        return 'calm'
    if score >= 55:
        return 'watch'
    if score >= 30:
        return 'elevated'
    return 'critical'


def webinars_owner_hint(row: dict[str, Any]) -> str:
    for candidate in ('owner', 'assignee', 'steward', 'manager', 'legal_owner', 'processor', 'host_name', 'sponsor'):
        value = str(row.get(candidate) or '').strip()
        if value:
            return value
    return 'unassigned-webinars'


def webinars_sla_hours(row: dict[str, Any]) -> int:
    band = webinars_risk_band(row)
    mapping = {'calm': 72, 'watch': 36, 'elevated': 12, 'critical': 4}
    return mapping[band]


def webinars_escalation_copy(row: dict[str, Any]) -> str:
    band = webinars_risk_band(row)
    owner = webinars_owner_hint(row)
    hours = webinars_sla_hours(row)
    return DOMAIN_TITLE + ' ' + band + ' item assigned to ' + owner + ' must move within ' + str(hours) + ' hours.'


PLAYBOOK_WEBINARS = [
    {'step': 1, 'title': 'Triage', 'domain': 'webinars', 'hint': 'Triage for Webinar Desk before the shift ends.'},
    {'step': 2, 'title': 'Confirm identifiers', 'domain': 'webinars', 'hint': 'Confirm identifiers for Webinar Desk before the shift ends.'},
    {'step': 3, 'title': 'Check policy exceptions', 'domain': 'webinars', 'hint': 'Check policy exceptions for Webinar Desk before the shift ends.'},
    {'step': 4, 'title': 'Notify the owner', 'domain': 'webinars', 'hint': 'Notify the owner for Webinar Desk before the shift ends.'},
    {'step': 5, 'title': 'Capture evidence', 'domain': 'webinars', 'hint': 'Capture evidence for Webinar Desk before the shift ends.'},
    {'step': 6, 'title': 'Propose a next status', 'domain': 'webinars', 'hint': 'Propose a next status for Webinar Desk before the shift ends.'},
    {'step': 7, 'title': 'Record the decision', 'domain': 'webinars', 'hint': 'Record the decision for Webinar Desk before the shift ends.'},
    {'step': 8, 'title': 'Close the loop with finance', 'domain': 'webinars', 'hint': 'Close the loop with finance for Webinar Desk before the shift ends.'},
    {'step': 9, 'title': 'File the audit crumb', 'domain': 'webinars', 'hint': 'File the audit crumb for Webinar Desk before the shift ends.'},
    {'step': 10, 'title': 'Schedule the next review', 'domain': 'webinars', 'hint': 'Schedule the next review for Webinar Desk before the shift ends.'},
]


def webinars_playbook() -> list[dict[str, Any]]:
    return list(PLAYBOOK_WEBINARS)


def webinars_exception_needed(row: dict[str, Any]) -> bool:
    return webinars_risk_band(row) in ('elevated', 'critical')


def webinars_freeze_window(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    return status in ['complete', 'cancelled'] and date.today().weekday() >= 5


def webinars_summary_line(row: dict[str, Any]) -> str:
    ident = str(row.get('id') or 'new')
    status = str(row.get('status') or 'n/a')
    band = webinars_risk_band(row)
    return DOMAIN_TITLE + ' ' + ident + ' is ' + status + ' (' + band + ').'

def webinars_check_webinar_code(value: Any) -> list[str]:
    """Field policy for Webinar Code inside Webinar Desk."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Webinar Code is required on Webinar Desk.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Webinar Code is zero; confirm the Webinar Desk case.')
        if number > 9_000_000_000:
            notes.append('Webinar Code exceeds the Webinar Desk ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Webinar Code must be YYYY-MM-DD for Webinar Desk.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Webinar Code is longer than the Webinar Desk ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Webinar Code placeholder values are not allowed on Webinar Desk.')
    return notes


def webinars_normalize_webinar_code(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def webinars_describe_webinar_code() -> str:
    required = 'required' if True else 'optional'
    return 'Webinar Code is a ' + required + ' str field on Webinar Desk (webinars).'


def webinars_check_title(value: Any) -> list[str]:
    """Field policy for Title inside Webinar Desk."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Title is required on Webinar Desk.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Title is zero; confirm the Webinar Desk case.')
        if number > 9_000_000_000:
            notes.append('Title exceeds the Webinar Desk ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Title must be YYYY-MM-DD for Webinar Desk.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Title is longer than the Webinar Desk ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Title placeholder values are not allowed on Webinar Desk.')
    return notes


def webinars_normalize_title(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def webinars_describe_title() -> str:
    required = 'required' if True else 'optional'
    return 'Title is a ' + required + ' str field on Webinar Desk (webinars).'


def webinars_check_host_name(value: Any) -> list[str]:
    """Field policy for Host Name inside Webinar Desk."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Host Name is required on Webinar Desk.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Host Name is zero; confirm the Webinar Desk case.')
        if number > 9_000_000_000:
            notes.append('Host Name exceeds the Webinar Desk ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Host Name must be YYYY-MM-DD for Webinar Desk.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Host Name is longer than the Webinar Desk ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Host Name placeholder values are not allowed on Webinar Desk.')
    return notes


def webinars_normalize_host_name(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def webinars_describe_host_name() -> str:
    required = 'required' if True else 'optional'
    return 'Host Name is a ' + required + ' str field on Webinar Desk (webinars).'


def webinars_check_starts_on(value: Any) -> list[str]:
    """Field policy for Starts On inside Webinar Desk."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Starts On is required on Webinar Desk.')
        return notes
    if 'date' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Starts On is zero; confirm the Webinar Desk case.')
        if number > 9_000_000_000:
            notes.append('Starts On exceeds the Webinar Desk ceiling.')
        return notes
    if 'date' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Starts On must be YYYY-MM-DD for Webinar Desk.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Starts On is longer than the Webinar Desk ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Starts On placeholder values are not allowed on Webinar Desk.')
    return notes


def webinars_normalize_starts_on(value: Any) -> Any:
    if 'date' == 'int':
        return _as_int(value)
    if 'date' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def webinars_describe_starts_on() -> str:
    required = 'required' if True else 'optional'
    return 'Starts On is a ' + required + ' date field on Webinar Desk (webinars).'


def webinars_check_cap(value: Any) -> list[str]:
    """Field policy for Cap inside Webinar Desk."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Cap is required on Webinar Desk.')
        return notes
    if 'int' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Cap is zero; confirm the Webinar Desk case.')
        if number > 9_000_000_000:
            notes.append('Cap exceeds the Webinar Desk ceiling.')
        return notes
    if 'int' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Cap must be YYYY-MM-DD for Webinar Desk.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Cap is longer than the Webinar Desk ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Cap placeholder values are not allowed on Webinar Desk.')
    return notes


def webinars_normalize_cap(value: Any) -> Any:
    if 'int' == 'int':
        return _as_int(value)
    if 'int' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def webinars_describe_cap() -> str:
    required = 'required' if True else 'optional'
    return 'Cap is a ' + required + ' int field on Webinar Desk (webinars).'


def webinars_check_status(value: Any) -> list[str]:
    """Field policy for Status inside Webinar Desk."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Status is required on Webinar Desk.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Status is zero; confirm the Webinar Desk case.')
        if number > 9_000_000_000:
            notes.append('Status exceeds the Webinar Desk ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Status must be YYYY-MM-DD for Webinar Desk.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Status is longer than the Webinar Desk ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Status placeholder values are not allowed on Webinar Desk.')
    return notes


def webinars_normalize_status(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def webinars_describe_status() -> str:
    required = 'required' if True else 'optional'
    return 'Status is a ' + required + ' str field on Webinar Desk (webinars).'


FIELD_CHECKS_WEBINARS = {
    'webinar_code': webinars_check_webinar_code,
    'title': webinars_check_title,
    'host_name': webinars_check_host_name,
    'starts_on': webinars_check_starts_on,
    'cap': webinars_check_cap,
    'status': webinars_check_status,
}


def webinars_run_field_checks(row: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for name, checker in FIELD_CHECKS_WEBINARS.items():
        found.extend(checker(row.get(name)))
    return found


def webinars_policy_card(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'domain': DOMAIN_KEY,
        'title': DOMAIN_TITLE,
        'band': webinars_risk_band(row),
        'owner': webinars_owner_hint(row),
        'sla_hours': webinars_sla_hours(row),
        'exceptions': webinars_exception_needed(row),
        'freeze': webinars_freeze_window(row),
        'violations': policy.collect(row) + webinars_run_field_checks(row),
        'summary': webinars_summary_line(row),
    }

