"""Policy engine for Meeting Rooms.

Bookable spaces with capacity and equipment notes.
Operators use these guards before a write is allowed to settle.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

DOMAIN_KEY = 'meeting_rooms'
DOMAIN_TITLE = 'Meeting Rooms'
ACCENT = '#d4d4d8'
STATUSES = ['open', 'held', 'offline']
SOFT_HOLD_STATUSES = ['held', 'offline']


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ''):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def meeting_rooms_policy_version() -> str:
    return 'meeting_rooms.policy.4'


def meeting_rooms_is_terminal(status: str) -> bool:
    return status == 'offline'


def meeting_rooms_requires_dual_control(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status in SOFT_HOLD_STATUSES:
        return True
    score = _as_int(row.get('health_score'))
    return score < 35


class MeetingRoomsPolicy:
    """Named checks that finance, people, and platform leads can quote."""

    def __init__(self) -> None:
        self.domain = 'meeting_rooms'
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
            self.violations.append('Meeting Rooms: status is missing.')
            return
        if status not in STATUSES:
            self.violations.append('Meeting Rooms: status is outside the published ladder.')

    def check_identity(self, row: dict[str, Any]) -> None:
        record_id = str(row.get('id') or '')
        if record_id and ' ' in record_id:
            self.violations.append('Meeting Rooms: record id cannot contain spaces.')

    def check_freshness(self, row: dict[str, Any]) -> None:
        stamp = str(row.get('updated_at') or '')
        if not stamp:
            return
        try:
            parsed = datetime.fromisoformat(stamp.replace('Z', ''))
        except ValueError:
            self.violations.append('Meeting Rooms: updated_at is not parseable.')
            return
        age = (datetime.utcnow() - parsed).days
        if age > 800:
            self.violations.append('Meeting Rooms: record is older than the archive window.')

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
                self.violations.append('Meeting Rooms: ' + name + ' is out of bounds.')

    def check_text_hygiene(self, row: dict[str, Any]) -> None:
        for name, value in row.items():
            if not isinstance(value, str):
                continue
            if '\x00' in value:
                self.violations.append('Meeting Rooms: ' + name + ' contains a null byte.')
            if value != value.strip() and name not in ('comment',):
                self.violations.append('Meeting Rooms: ' + name + ' has surrounding whitespace.')

    def check_lifecycle(self, row: dict[str, Any]) -> None:
        status = str(row.get('status') or '')
        if status == 'offline' and _as_int(row.get('health_score')) > 90:
            self.violations.append('Meeting Rooms: terminal status with a high health score needs a note.')

    def allow_write(self, row: dict[str, Any]) -> bool:
        return not self.collect(row)


policy = MeetingRoomsPolicy()


def meeting_rooms_gate_create(payload: dict[str, Any]) -> list[str]:
    return policy.collect(payload)


def meeting_rooms_gate_transition(current: str, nxt: str) -> list[str]:
    errors: list[str] = []
    if nxt not in STATUSES:
        errors.append('Meeting Rooms cannot move to an unknown status.')
    if current == 'offline' and nxt != current:
        if nxt not in STATUSES[:1]:
            errors.append('Meeting Rooms is sealed; only a reopen to the first status is modeled.')
    return errors


def meeting_rooms_risk_band(row: dict[str, Any]) -> str:
    score = _as_int(row.get('health_score'))
    if score >= 80:
        return 'calm'
    if score >= 55:
        return 'watch'
    if score >= 30:
        return 'elevated'
    return 'critical'


def meeting_rooms_owner_hint(row: dict[str, Any]) -> str:
    for candidate in ('owner', 'assignee', 'steward', 'manager', 'legal_owner', 'processor', 'host_name', 'sponsor'):
        value = str(row.get(candidate) or '').strip()
        if value:
            return value
    return 'unassigned-meeting_rooms'


def meeting_rooms_sla_hours(row: dict[str, Any]) -> int:
    band = meeting_rooms_risk_band(row)
    mapping = {'calm': 72, 'watch': 36, 'elevated': 12, 'critical': 4}
    return mapping[band]


def meeting_rooms_escalation_copy(row: dict[str, Any]) -> str:
    band = meeting_rooms_risk_band(row)
    owner = meeting_rooms_owner_hint(row)
    hours = meeting_rooms_sla_hours(row)
    return DOMAIN_TITLE + ' ' + band + ' item assigned to ' + owner + ' must move within ' + str(hours) + ' hours.'


PLAYBOOK_MEETING_ROOMS = [
    {'step': 1, 'title': 'Triage', 'domain': 'meeting_rooms', 'hint': 'Triage for Meeting Rooms before the shift ends.'},
    {'step': 2, 'title': 'Confirm identifiers', 'domain': 'meeting_rooms', 'hint': 'Confirm identifiers for Meeting Rooms before the shift ends.'},
    {'step': 3, 'title': 'Check policy exceptions', 'domain': 'meeting_rooms', 'hint': 'Check policy exceptions for Meeting Rooms before the shift ends.'},
    {'step': 4, 'title': 'Notify the owner', 'domain': 'meeting_rooms', 'hint': 'Notify the owner for Meeting Rooms before the shift ends.'},
    {'step': 5, 'title': 'Capture evidence', 'domain': 'meeting_rooms', 'hint': 'Capture evidence for Meeting Rooms before the shift ends.'},
    {'step': 6, 'title': 'Propose a next status', 'domain': 'meeting_rooms', 'hint': 'Propose a next status for Meeting Rooms before the shift ends.'},
    {'step': 7, 'title': 'Record the decision', 'domain': 'meeting_rooms', 'hint': 'Record the decision for Meeting Rooms before the shift ends.'},
    {'step': 8, 'title': 'Close the loop with finance', 'domain': 'meeting_rooms', 'hint': 'Close the loop with finance for Meeting Rooms before the shift ends.'},
    {'step': 9, 'title': 'File the audit crumb', 'domain': 'meeting_rooms', 'hint': 'File the audit crumb for Meeting Rooms before the shift ends.'},
    {'step': 10, 'title': 'Schedule the next review', 'domain': 'meeting_rooms', 'hint': 'Schedule the next review for Meeting Rooms before the shift ends.'},
]


def meeting_rooms_playbook() -> list[dict[str, Any]]:
    return list(PLAYBOOK_MEETING_ROOMS)


def meeting_rooms_exception_needed(row: dict[str, Any]) -> bool:
    return meeting_rooms_risk_band(row) in ('elevated', 'critical')


def meeting_rooms_freeze_window(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    return status in ['held', 'offline'] and date.today().weekday() >= 5


def meeting_rooms_summary_line(row: dict[str, Any]) -> str:
    ident = str(row.get('id') or 'new')
    status = str(row.get('status') or 'n/a')
    band = meeting_rooms_risk_band(row)
    return DOMAIN_TITLE + ' ' + ident + ' is ' + status + ' (' + band + ').'

def meeting_rooms_check_room_code(value: Any) -> list[str]:
    """Field policy for Room Code inside Meeting Rooms."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Room Code is required on Meeting Rooms.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Room Code is zero; confirm the Meeting Rooms case.')
        if number > 9_000_000_000:
            notes.append('Room Code exceeds the Meeting Rooms ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Room Code must be YYYY-MM-DD for Meeting Rooms.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Room Code is longer than the Meeting Rooms ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Room Code placeholder values are not allowed on Meeting Rooms.')
    return notes


def meeting_rooms_normalize_room_code(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def meeting_rooms_describe_room_code() -> str:
    required = 'required' if True else 'optional'
    return 'Room Code is a ' + required + ' str field on Meeting Rooms (meeting_rooms).'


def meeting_rooms_check_floor(value: Any) -> list[str]:
    """Field policy for Floor inside Meeting Rooms."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Floor is required on Meeting Rooms.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Floor is zero; confirm the Meeting Rooms case.')
        if number > 9_000_000_000:
            notes.append('Floor exceeds the Meeting Rooms ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Floor must be YYYY-MM-DD for Meeting Rooms.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Floor is longer than the Meeting Rooms ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Floor placeholder values are not allowed on Meeting Rooms.')
    return notes


def meeting_rooms_normalize_floor(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def meeting_rooms_describe_floor() -> str:
    required = 'required' if True else 'optional'
    return 'Floor is a ' + required + ' str field on Meeting Rooms (meeting_rooms).'


def meeting_rooms_check_capacity(value: Any) -> list[str]:
    """Field policy for Capacity inside Meeting Rooms."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Capacity is required on Meeting Rooms.')
        return notes
    if 'int' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Capacity is zero; confirm the Meeting Rooms case.')
        if number > 9_000_000_000:
            notes.append('Capacity exceeds the Meeting Rooms ceiling.')
        return notes
    if 'int' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Capacity must be YYYY-MM-DD for Meeting Rooms.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Capacity is longer than the Meeting Rooms ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Capacity placeholder values are not allowed on Meeting Rooms.')
    return notes


def meeting_rooms_normalize_capacity(value: Any) -> Any:
    if 'int' == 'int':
        return _as_int(value)
    if 'int' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def meeting_rooms_describe_capacity() -> str:
    required = 'required' if True else 'optional'
    return 'Capacity is a ' + required + ' int field on Meeting Rooms (meeting_rooms).'


def meeting_rooms_check_equipment(value: Any) -> list[str]:
    """Field policy for Equipment inside Meeting Rooms."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Equipment is required on Meeting Rooms.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Equipment is zero; confirm the Meeting Rooms case.')
        if number > 9_000_000_000:
            notes.append('Equipment exceeds the Meeting Rooms ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Equipment must be YYYY-MM-DD for Meeting Rooms.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Equipment is longer than the Meeting Rooms ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Equipment placeholder values are not allowed on Meeting Rooms.')
    return notes


def meeting_rooms_normalize_equipment(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def meeting_rooms_describe_equipment() -> str:
    required = 'required' if True else 'optional'
    return 'Equipment is a ' + required + ' str field on Meeting Rooms (meeting_rooms).'


def meeting_rooms_check_status(value: Any) -> list[str]:
    """Field policy for Status inside Meeting Rooms."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Status is required on Meeting Rooms.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Status is zero; confirm the Meeting Rooms case.')
        if number > 9_000_000_000:
            notes.append('Status exceeds the Meeting Rooms ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Status must be YYYY-MM-DD for Meeting Rooms.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Status is longer than the Meeting Rooms ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Status placeholder values are not allowed on Meeting Rooms.')
    return notes


def meeting_rooms_normalize_status(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def meeting_rooms_describe_status() -> str:
    required = 'required' if True else 'optional'
    return 'Status is a ' + required + ' str field on Meeting Rooms (meeting_rooms).'


FIELD_CHECKS_MEETING_ROOMS = {
    'room_code': meeting_rooms_check_room_code,
    'floor': meeting_rooms_check_floor,
    'capacity': meeting_rooms_check_capacity,
    'equipment': meeting_rooms_check_equipment,
    'status': meeting_rooms_check_status,
}


def meeting_rooms_run_field_checks(row: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for name, checker in FIELD_CHECKS_MEETING_ROOMS.items():
        found.extend(checker(row.get(name)))
    return found


def meeting_rooms_policy_card(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'domain': DOMAIN_KEY,
        'title': DOMAIN_TITLE,
        'band': meeting_rooms_risk_band(row),
        'owner': meeting_rooms_owner_hint(row),
        'sla_hours': meeting_rooms_sla_hours(row),
        'exceptions': meeting_rooms_exception_needed(row),
        'freeze': meeting_rooms_freeze_window(row),
        'violations': policy.collect(row) + meeting_rooms_run_field_checks(row),
        'summary': meeting_rooms_summary_line(row),
    }

