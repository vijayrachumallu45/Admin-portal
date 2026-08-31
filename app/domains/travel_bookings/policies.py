"""Policy engine for Travel Bookings.

Trips, rails, and lodging holds against travel policy.
Operators use these guards before a write is allowed to settle.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

DOMAIN_KEY = 'travel_bookings'
DOMAIN_TITLE = 'Travel Bookings'
ACCENT = '#38bdf8'
STATUSES = ['held', 'ticketed', 'in_trip', 'complete', 'void']
SOFT_HOLD_STATUSES = ['complete', 'void']


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ''):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def travel_bookings_policy_version() -> str:
    return 'travel_bookings.policy.4'


def travel_bookings_is_terminal(status: str) -> bool:
    return status == 'void'


def travel_bookings_requires_dual_control(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status in SOFT_HOLD_STATUSES:
        return True
    score = _as_int(row.get('health_score'))
    return score < 35


class TravelBookingsPolicy:
    """Named checks that finance, people, and platform leads can quote."""

    def __init__(self) -> None:
        self.domain = 'travel_bookings'
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
            self.violations.append('Travel Bookings: status is missing.')
            return
        if status not in STATUSES:
            self.violations.append('Travel Bookings: status is outside the published ladder.')

    def check_identity(self, row: dict[str, Any]) -> None:
        record_id = str(row.get('id') or '')
        if record_id and ' ' in record_id:
            self.violations.append('Travel Bookings: record id cannot contain spaces.')

    def check_freshness(self, row: dict[str, Any]) -> None:
        stamp = str(row.get('updated_at') or '')
        if not stamp:
            return
        try:
            parsed = datetime.fromisoformat(stamp.replace('Z', ''))
        except ValueError:
            self.violations.append('Travel Bookings: updated_at is not parseable.')
            return
        age = (datetime.utcnow() - parsed).days
        if age > 800:
            self.violations.append('Travel Bookings: record is older than the archive window.')

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
                self.violations.append('Travel Bookings: ' + name + ' is out of bounds.')

    def check_text_hygiene(self, row: dict[str, Any]) -> None:
        for name, value in row.items():
            if not isinstance(value, str):
                continue
            if '\x00' in value:
                self.violations.append('Travel Bookings: ' + name + ' contains a null byte.')
            if value != value.strip() and name not in ('comment',):
                self.violations.append('Travel Bookings: ' + name + ' has surrounding whitespace.')

    def check_lifecycle(self, row: dict[str, Any]) -> None:
        status = str(row.get('status') or '')
        if status == 'void' and _as_int(row.get('health_score')) > 90:
            self.violations.append('Travel Bookings: terminal status with a high health score needs a note.')

    def allow_write(self, row: dict[str, Any]) -> bool:
        return not self.collect(row)


policy = TravelBookingsPolicy()


def travel_bookings_gate_create(payload: dict[str, Any]) -> list[str]:
    return policy.collect(payload)


def travel_bookings_gate_transition(current: str, nxt: str) -> list[str]:
    errors: list[str] = []
    if nxt not in STATUSES:
        errors.append('Travel Bookings cannot move to an unknown status.')
    if current == 'void' and nxt != current:
        if nxt not in STATUSES[:1]:
            errors.append('Travel Bookings is sealed; only a reopen to the first status is modeled.')
    return errors


def travel_bookings_risk_band(row: dict[str, Any]) -> str:
    score = _as_int(row.get('health_score'))
    if score >= 80:
        return 'calm'
    if score >= 55:
        return 'watch'
    if score >= 30:
        return 'elevated'
    return 'critical'


def travel_bookings_owner_hint(row: dict[str, Any]) -> str:
    for candidate in ('owner', 'assignee', 'steward', 'manager', 'legal_owner', 'processor', 'host_name', 'sponsor'):
        value = str(row.get(candidate) or '').strip()
        if value:
            return value
    return 'unassigned-travel_bookings'


def travel_bookings_sla_hours(row: dict[str, Any]) -> int:
    band = travel_bookings_risk_band(row)
    mapping = {'calm': 72, 'watch': 36, 'elevated': 12, 'critical': 4}
    return mapping[band]


def travel_bookings_escalation_copy(row: dict[str, Any]) -> str:
    band = travel_bookings_risk_band(row)
    owner = travel_bookings_owner_hint(row)
    hours = travel_bookings_sla_hours(row)
    return DOMAIN_TITLE + ' ' + band + ' item assigned to ' + owner + ' must move within ' + str(hours) + ' hours.'


PLAYBOOK_TRAVEL_BOOKINGS = [
    {'step': 1, 'title': 'Triage', 'domain': 'travel_bookings', 'hint': 'Triage for Travel Bookings before the shift ends.'},
    {'step': 2, 'title': 'Confirm identifiers', 'domain': 'travel_bookings', 'hint': 'Confirm identifiers for Travel Bookings before the shift ends.'},
    {'step': 3, 'title': 'Check policy exceptions', 'domain': 'travel_bookings', 'hint': 'Check policy exceptions for Travel Bookings before the shift ends.'},
    {'step': 4, 'title': 'Notify the owner', 'domain': 'travel_bookings', 'hint': 'Notify the owner for Travel Bookings before the shift ends.'},
    {'step': 5, 'title': 'Capture evidence', 'domain': 'travel_bookings', 'hint': 'Capture evidence for Travel Bookings before the shift ends.'},
    {'step': 6, 'title': 'Propose a next status', 'domain': 'travel_bookings', 'hint': 'Propose a next status for Travel Bookings before the shift ends.'},
    {'step': 7, 'title': 'Record the decision', 'domain': 'travel_bookings', 'hint': 'Record the decision for Travel Bookings before the shift ends.'},
    {'step': 8, 'title': 'Close the loop with finance', 'domain': 'travel_bookings', 'hint': 'Close the loop with finance for Travel Bookings before the shift ends.'},
    {'step': 9, 'title': 'File the audit crumb', 'domain': 'travel_bookings', 'hint': 'File the audit crumb for Travel Bookings before the shift ends.'},
    {'step': 10, 'title': 'Schedule the next review', 'domain': 'travel_bookings', 'hint': 'Schedule the next review for Travel Bookings before the shift ends.'},
]


def travel_bookings_playbook() -> list[dict[str, Any]]:
    return list(PLAYBOOK_TRAVEL_BOOKINGS)


def travel_bookings_exception_needed(row: dict[str, Any]) -> bool:
    return travel_bookings_risk_band(row) in ('elevated', 'critical')


def travel_bookings_freeze_window(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    return status in ['complete', 'void'] and date.today().weekday() >= 5


def travel_bookings_summary_line(row: dict[str, Any]) -> str:
    ident = str(row.get('id') or 'new')
    status = str(row.get('status') or 'n/a')
    band = travel_bookings_risk_band(row)
    return DOMAIN_TITLE + ' ' + ident + ' is ' + status + ' (' + band + ').'

def travel_bookings_check_booking_no(value: Any) -> list[str]:
    """Field policy for Booking No inside Travel Bookings."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Booking No is required on Travel Bookings.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Booking No is zero; confirm the Travel Bookings case.')
        if number > 9_000_000_000:
            notes.append('Booking No exceeds the Travel Bookings ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Booking No must be YYYY-MM-DD for Travel Bookings.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Booking No is longer than the Travel Bookings ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Booking No placeholder values are not allowed on Travel Bookings.')
    return notes


def travel_bookings_normalize_booking_no(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def travel_bookings_describe_booking_no() -> str:
    required = 'required' if True else 'optional'
    return 'Booking No is a ' + required + ' str field on Travel Bookings (travel_bookings).'


def travel_bookings_check_traveler(value: Any) -> list[str]:
    """Field policy for Traveler inside Travel Bookings."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Traveler is required on Travel Bookings.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Traveler is zero; confirm the Travel Bookings case.')
        if number > 9_000_000_000:
            notes.append('Traveler exceeds the Travel Bookings ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Traveler must be YYYY-MM-DD for Travel Bookings.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Traveler is longer than the Travel Bookings ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Traveler placeholder values are not allowed on Travel Bookings.')
    return notes


def travel_bookings_normalize_traveler(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def travel_bookings_describe_traveler() -> str:
    required = 'required' if True else 'optional'
    return 'Traveler is a ' + required + ' str field on Travel Bookings (travel_bookings).'


def travel_bookings_check_origin(value: Any) -> list[str]:
    """Field policy for Origin inside Travel Bookings."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Origin is required on Travel Bookings.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Origin is zero; confirm the Travel Bookings case.')
        if number > 9_000_000_000:
            notes.append('Origin exceeds the Travel Bookings ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Origin must be YYYY-MM-DD for Travel Bookings.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Origin is longer than the Travel Bookings ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Origin placeholder values are not allowed on Travel Bookings.')
    return notes


def travel_bookings_normalize_origin(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def travel_bookings_describe_origin() -> str:
    required = 'required' if True else 'optional'
    return 'Origin is a ' + required + ' str field on Travel Bookings (travel_bookings).'


def travel_bookings_check_destination(value: Any) -> list[str]:
    """Field policy for Destination inside Travel Bookings."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Destination is required on Travel Bookings.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Destination is zero; confirm the Travel Bookings case.')
        if number > 9_000_000_000:
            notes.append('Destination exceeds the Travel Bookings ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Destination must be YYYY-MM-DD for Travel Bookings.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Destination is longer than the Travel Bookings ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Destination placeholder values are not allowed on Travel Bookings.')
    return notes


def travel_bookings_normalize_destination(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def travel_bookings_describe_destination() -> str:
    required = 'required' if True else 'optional'
    return 'Destination is a ' + required + ' str field on Travel Bookings (travel_bookings).'


def travel_bookings_check_departs_on(value: Any) -> list[str]:
    """Field policy for Departs On inside Travel Bookings."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Departs On is required on Travel Bookings.')
        return notes
    if 'date' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Departs On is zero; confirm the Travel Bookings case.')
        if number > 9_000_000_000:
            notes.append('Departs On exceeds the Travel Bookings ceiling.')
        return notes
    if 'date' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Departs On must be YYYY-MM-DD for Travel Bookings.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Departs On is longer than the Travel Bookings ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Departs On placeholder values are not allowed on Travel Bookings.')
    return notes


def travel_bookings_normalize_departs_on(value: Any) -> Any:
    if 'date' == 'int':
        return _as_int(value)
    if 'date' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def travel_bookings_describe_departs_on() -> str:
    required = 'required' if True else 'optional'
    return 'Departs On is a ' + required + ' date field on Travel Bookings (travel_bookings).'


def travel_bookings_check_status(value: Any) -> list[str]:
    """Field policy for Status inside Travel Bookings."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Status is required on Travel Bookings.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Status is zero; confirm the Travel Bookings case.')
        if number > 9_000_000_000:
            notes.append('Status exceeds the Travel Bookings ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Status must be YYYY-MM-DD for Travel Bookings.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Status is longer than the Travel Bookings ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Status placeholder values are not allowed on Travel Bookings.')
    return notes


def travel_bookings_normalize_status(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def travel_bookings_describe_status() -> str:
    required = 'required' if True else 'optional'
    return 'Status is a ' + required + ' str field on Travel Bookings (travel_bookings).'


FIELD_CHECKS_TRAVEL_BOOKINGS = {
    'booking_no': travel_bookings_check_booking_no,
    'traveler': travel_bookings_check_traveler,
    'origin': travel_bookings_check_origin,
    'destination': travel_bookings_check_destination,
    'departs_on': travel_bookings_check_departs_on,
    'status': travel_bookings_check_status,
}


def travel_bookings_run_field_checks(row: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for name, checker in FIELD_CHECKS_TRAVEL_BOOKINGS.items():
        found.extend(checker(row.get(name)))
    return found


def travel_bookings_policy_card(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'domain': DOMAIN_KEY,
        'title': DOMAIN_TITLE,
        'band': travel_bookings_risk_band(row),
        'owner': travel_bookings_owner_hint(row),
        'sla_hours': travel_bookings_sla_hours(row),
        'exceptions': travel_bookings_exception_needed(row),
        'freeze': travel_bookings_freeze_window(row),
        'violations': policy.collect(row) + travel_bookings_run_field_checks(row),
        'summary': travel_bookings_summary_line(row),
    }

