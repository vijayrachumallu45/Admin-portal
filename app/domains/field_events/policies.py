"""Policy engine for Field Events.

Conferences and roadshows with booth kits and spend caps.
Operators use these guards before a write is allowed to settle.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

DOMAIN_KEY = 'field_events'
DOMAIN_TITLE = 'Field Events'
ACCENT = '#22d3ee'
STATUSES = ['proposed', 'booked', 'live', 'wrap']
SOFT_HOLD_STATUSES = ['live', 'wrap']


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ''):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def field_events_policy_version() -> str:
    return 'field_events.policy.4'


def field_events_is_terminal(status: str) -> bool:
    return status == 'wrap'


def field_events_requires_dual_control(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status in SOFT_HOLD_STATUSES:
        return True
    score = _as_int(row.get('health_score'))
    return score < 35


class FieldEventsPolicy:
    """Named checks that finance, people, and platform leads can quote."""

    def __init__(self) -> None:
        self.domain = 'field_events'
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
            self.violations.append('Field Events: status is missing.')
            return
        if status not in STATUSES:
            self.violations.append('Field Events: status is outside the published ladder.')

    def check_identity(self, row: dict[str, Any]) -> None:
        record_id = str(row.get('id') or '')
        if record_id and ' ' in record_id:
            self.violations.append('Field Events: record id cannot contain spaces.')

    def check_freshness(self, row: dict[str, Any]) -> None:
        stamp = str(row.get('updated_at') or '')
        if not stamp:
            return
        try:
            parsed = datetime.fromisoformat(stamp.replace('Z', ''))
        except ValueError:
            self.violations.append('Field Events: updated_at is not parseable.')
            return
        age = (datetime.utcnow() - parsed).days
        if age > 800:
            self.violations.append('Field Events: record is older than the archive window.')

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
                self.violations.append('Field Events: ' + name + ' is out of bounds.')

    def check_text_hygiene(self, row: dict[str, Any]) -> None:
        for name, value in row.items():
            if not isinstance(value, str):
                continue
            if '\x00' in value:
                self.violations.append('Field Events: ' + name + ' contains a null byte.')
            if value != value.strip() and name not in ('comment',):
                self.violations.append('Field Events: ' + name + ' has surrounding whitespace.')

    def check_lifecycle(self, row: dict[str, Any]) -> None:
        status = str(row.get('status') or '')
        if status == 'wrap' and _as_int(row.get('health_score')) > 90:
            self.violations.append('Field Events: terminal status with a high health score needs a note.')

    def allow_write(self, row: dict[str, Any]) -> bool:
        return not self.collect(row)


policy = FieldEventsPolicy()


def field_events_gate_create(payload: dict[str, Any]) -> list[str]:
    return policy.collect(payload)


def field_events_gate_transition(current: str, nxt: str) -> list[str]:
    errors: list[str] = []
    if nxt not in STATUSES:
        errors.append('Field Events cannot move to an unknown status.')
    if current == 'wrap' and nxt != current:
        if nxt not in STATUSES[:1]:
            errors.append('Field Events is sealed; only a reopen to the first status is modeled.')
    return errors


def field_events_risk_band(row: dict[str, Any]) -> str:
    score = _as_int(row.get('health_score'))
    if score >= 80:
        return 'calm'
    if score >= 55:
        return 'watch'
    if score >= 30:
        return 'elevated'
    return 'critical'


def field_events_owner_hint(row: dict[str, Any]) -> str:
    for candidate in ('owner', 'assignee', 'steward', 'manager', 'legal_owner', 'processor', 'host_name', 'sponsor'):
        value = str(row.get(candidate) or '').strip()
        if value:
            return value
    return 'unassigned-field_events'


def field_events_sla_hours(row: dict[str, Any]) -> int:
    band = field_events_risk_band(row)
    mapping = {'calm': 72, 'watch': 36, 'elevated': 12, 'critical': 4}
    return mapping[band]


def field_events_escalation_copy(row: dict[str, Any]) -> str:
    band = field_events_risk_band(row)
    owner = field_events_owner_hint(row)
    hours = field_events_sla_hours(row)
    return DOMAIN_TITLE + ' ' + band + ' item assigned to ' + owner + ' must move within ' + str(hours) + ' hours.'


PLAYBOOK_FIELD_EVENTS = [
    {'step': 1, 'title': 'Triage', 'domain': 'field_events', 'hint': 'Triage for Field Events before the shift ends.'},
    {'step': 2, 'title': 'Confirm identifiers', 'domain': 'field_events', 'hint': 'Confirm identifiers for Field Events before the shift ends.'},
    {'step': 3, 'title': 'Check policy exceptions', 'domain': 'field_events', 'hint': 'Check policy exceptions for Field Events before the shift ends.'},
    {'step': 4, 'title': 'Notify the owner', 'domain': 'field_events', 'hint': 'Notify the owner for Field Events before the shift ends.'},
    {'step': 5, 'title': 'Capture evidence', 'domain': 'field_events', 'hint': 'Capture evidence for Field Events before the shift ends.'},
    {'step': 6, 'title': 'Propose a next status', 'domain': 'field_events', 'hint': 'Propose a next status for Field Events before the shift ends.'},
    {'step': 7, 'title': 'Record the decision', 'domain': 'field_events', 'hint': 'Record the decision for Field Events before the shift ends.'},
    {'step': 8, 'title': 'Close the loop with finance', 'domain': 'field_events', 'hint': 'Close the loop with finance for Field Events before the shift ends.'},
    {'step': 9, 'title': 'File the audit crumb', 'domain': 'field_events', 'hint': 'File the audit crumb for Field Events before the shift ends.'},
    {'step': 10, 'title': 'Schedule the next review', 'domain': 'field_events', 'hint': 'Schedule the next review for Field Events before the shift ends.'},
]


def field_events_playbook() -> list[dict[str, Any]]:
    return list(PLAYBOOK_FIELD_EVENTS)


def field_events_exception_needed(row: dict[str, Any]) -> bool:
    return field_events_risk_band(row) in ('elevated', 'critical')


def field_events_freeze_window(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    return status in ['live', 'wrap'] and date.today().weekday() >= 5


def field_events_summary_line(row: dict[str, Any]) -> str:
    ident = str(row.get('id') or 'new')
    status = str(row.get('status') or 'n/a')
    band = field_events_risk_band(row)
    return DOMAIN_TITLE + ' ' + ident + ' is ' + status + ' (' + band + ').'

def field_events_check_event_code(value: Any) -> list[str]:
    """Field policy for Event Code inside Field Events."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Event Code is required on Field Events.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Event Code is zero; confirm the Field Events case.')
        if number > 9_000_000_000:
            notes.append('Event Code exceeds the Field Events ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Event Code must be YYYY-MM-DD for Field Events.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Event Code is longer than the Field Events ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Event Code placeholder values are not allowed on Field Events.')
    return notes


def field_events_normalize_event_code(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def field_events_describe_event_code() -> str:
    required = 'required' if True else 'optional'
    return 'Event Code is a ' + required + ' str field on Field Events (field_events).'


def field_events_check_city(value: Any) -> list[str]:
    """Field policy for City inside Field Events."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('City is required on Field Events.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('City is zero; confirm the Field Events case.')
        if number > 9_000_000_000:
            notes.append('City exceeds the Field Events ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('City must be YYYY-MM-DD for Field Events.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('City is longer than the Field Events ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('City placeholder values are not allowed on Field Events.')
    return notes


def field_events_normalize_city(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def field_events_describe_city() -> str:
    required = 'required' if True else 'optional'
    return 'City is a ' + required + ' str field on Field Events (field_events).'


def field_events_check_starts_on(value: Any) -> list[str]:
    """Field policy for Starts On inside Field Events."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Starts On is required on Field Events.')
        return notes
    if 'date' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Starts On is zero; confirm the Field Events case.')
        if number > 9_000_000_000:
            notes.append('Starts On exceeds the Field Events ceiling.')
        return notes
    if 'date' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Starts On must be YYYY-MM-DD for Field Events.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Starts On is longer than the Field Events ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Starts On placeholder values are not allowed on Field Events.')
    return notes


def field_events_normalize_starts_on(value: Any) -> Any:
    if 'date' == 'int':
        return _as_int(value)
    if 'date' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def field_events_describe_starts_on() -> str:
    required = 'required' if True else 'optional'
    return 'Starts On is a ' + required + ' date field on Field Events (field_events).'


def field_events_check_budget_cents(value: Any) -> list[str]:
    """Field policy for Budget Cents inside Field Events."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Budget Cents is required on Field Events.')
        return notes
    if 'int' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Budget Cents is zero; confirm the Field Events case.')
        if number > 9_000_000_000:
            notes.append('Budget Cents exceeds the Field Events ceiling.')
        return notes
    if 'int' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Budget Cents must be YYYY-MM-DD for Field Events.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Budget Cents is longer than the Field Events ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Budget Cents placeholder values are not allowed on Field Events.')
    return notes


def field_events_normalize_budget_cents(value: Any) -> Any:
    if 'int' == 'int':
        return _as_int(value)
    if 'int' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def field_events_describe_budget_cents() -> str:
    required = 'required' if True else 'optional'
    return 'Budget Cents is a ' + required + ' int field on Field Events (field_events).'


def field_events_check_status(value: Any) -> list[str]:
    """Field policy for Status inside Field Events."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Status is required on Field Events.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Status is zero; confirm the Field Events case.')
        if number > 9_000_000_000:
            notes.append('Status exceeds the Field Events ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Status must be YYYY-MM-DD for Field Events.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Status is longer than the Field Events ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Status placeholder values are not allowed on Field Events.')
    return notes


def field_events_normalize_status(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def field_events_describe_status() -> str:
    required = 'required' if True else 'optional'
    return 'Status is a ' + required + ' str field on Field Events (field_events).'


FIELD_CHECKS_FIELD_EVENTS = {
    'event_code': field_events_check_event_code,
    'city': field_events_check_city,
    'starts_on': field_events_check_starts_on,
    'budget_cents': field_events_check_budget_cents,
    'status': field_events_check_status,
}


def field_events_run_field_checks(row: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for name, checker in FIELD_CHECKS_FIELD_EVENTS.items():
        found.extend(checker(row.get(name)))
    return found


def field_events_policy_card(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'domain': DOMAIN_KEY,
        'title': DOMAIN_TITLE,
        'band': field_events_risk_band(row),
        'owner': field_events_owner_hint(row),
        'sla_hours': field_events_sla_hours(row),
        'exceptions': field_events_exception_needed(row),
        'freeze': field_events_freeze_window(row),
        'violations': policy.collect(row) + field_events_run_field_checks(row),
        'summary': field_events_summary_line(row),
    }

