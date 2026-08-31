"""Policy engine for Board Packs.

Director packs with freeze dates and distribution lists.
Operators use these guards before a write is allowed to settle.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

DOMAIN_KEY = 'board_packs'
DOMAIN_TITLE = 'Board Packs'
ACCENT = '#e2e8f0'
STATUSES = ['collecting', 'frozen', 'sent']
SOFT_HOLD_STATUSES = ['frozen', 'sent']


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ''):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def board_packs_policy_version() -> str:
    return 'board_packs.policy.4'


def board_packs_is_terminal(status: str) -> bool:
    return status == 'sent'


def board_packs_requires_dual_control(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status in SOFT_HOLD_STATUSES:
        return True
    score = _as_int(row.get('health_score'))
    return score < 35


class BoardPacksPolicy:
    """Named checks that finance, people, and platform leads can quote."""

    def __init__(self) -> None:
        self.domain = 'board_packs'
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
            self.violations.append('Board Packs: status is missing.')
            return
        if status not in STATUSES:
            self.violations.append('Board Packs: status is outside the published ladder.')

    def check_identity(self, row: dict[str, Any]) -> None:
        record_id = str(row.get('id') or '')
        if record_id and ' ' in record_id:
            self.violations.append('Board Packs: record id cannot contain spaces.')

    def check_freshness(self, row: dict[str, Any]) -> None:
        stamp = str(row.get('updated_at') or '')
        if not stamp:
            return
        try:
            parsed = datetime.fromisoformat(stamp.replace('Z', ''))
        except ValueError:
            self.violations.append('Board Packs: updated_at is not parseable.')
            return
        age = (datetime.utcnow() - parsed).days
        if age > 800:
            self.violations.append('Board Packs: record is older than the archive window.')

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
                self.violations.append('Board Packs: ' + name + ' is out of bounds.')

    def check_text_hygiene(self, row: dict[str, Any]) -> None:
        for name, value in row.items():
            if not isinstance(value, str):
                continue
            if '\x00' in value:
                self.violations.append('Board Packs: ' + name + ' contains a null byte.')
            if value != value.strip() and name not in ('comment',):
                self.violations.append('Board Packs: ' + name + ' has surrounding whitespace.')

    def check_lifecycle(self, row: dict[str, Any]) -> None:
        status = str(row.get('status') or '')
        if status == 'sent' and _as_int(row.get('health_score')) > 90:
            self.violations.append('Board Packs: terminal status with a high health score needs a note.')

    def allow_write(self, row: dict[str, Any]) -> bool:
        return not self.collect(row)


policy = BoardPacksPolicy()


def board_packs_gate_create(payload: dict[str, Any]) -> list[str]:
    return policy.collect(payload)


def board_packs_gate_transition(current: str, nxt: str) -> list[str]:
    errors: list[str] = []
    if nxt not in STATUSES:
        errors.append('Board Packs cannot move to an unknown status.')
    if current == 'sent' and nxt != current:
        if nxt not in STATUSES[:1]:
            errors.append('Board Packs is sealed; only a reopen to the first status is modeled.')
    return errors


def board_packs_risk_band(row: dict[str, Any]) -> str:
    score = _as_int(row.get('health_score'))
    if score >= 80:
        return 'calm'
    if score >= 55:
        return 'watch'
    if score >= 30:
        return 'elevated'
    return 'critical'


def board_packs_owner_hint(row: dict[str, Any]) -> str:
    for candidate in ('owner', 'assignee', 'steward', 'manager', 'legal_owner', 'processor', 'host_name', 'sponsor'):
        value = str(row.get(candidate) or '').strip()
        if value:
            return value
    return 'unassigned-board_packs'


def board_packs_sla_hours(row: dict[str, Any]) -> int:
    band = board_packs_risk_band(row)
    mapping = {'calm': 72, 'watch': 36, 'elevated': 12, 'critical': 4}
    return mapping[band]


def board_packs_escalation_copy(row: dict[str, Any]) -> str:
    band = board_packs_risk_band(row)
    owner = board_packs_owner_hint(row)
    hours = board_packs_sla_hours(row)
    return DOMAIN_TITLE + ' ' + band + ' item assigned to ' + owner + ' must move within ' + str(hours) + ' hours.'


PLAYBOOK_BOARD_PACKS = [
    {'step': 1, 'title': 'Triage', 'domain': 'board_packs', 'hint': 'Triage for Board Packs before the shift ends.'},
    {'step': 2, 'title': 'Confirm identifiers', 'domain': 'board_packs', 'hint': 'Confirm identifiers for Board Packs before the shift ends.'},
    {'step': 3, 'title': 'Check policy exceptions', 'domain': 'board_packs', 'hint': 'Check policy exceptions for Board Packs before the shift ends.'},
    {'step': 4, 'title': 'Notify the owner', 'domain': 'board_packs', 'hint': 'Notify the owner for Board Packs before the shift ends.'},
    {'step': 5, 'title': 'Capture evidence', 'domain': 'board_packs', 'hint': 'Capture evidence for Board Packs before the shift ends.'},
    {'step': 6, 'title': 'Propose a next status', 'domain': 'board_packs', 'hint': 'Propose a next status for Board Packs before the shift ends.'},
    {'step': 7, 'title': 'Record the decision', 'domain': 'board_packs', 'hint': 'Record the decision for Board Packs before the shift ends.'},
    {'step': 8, 'title': 'Close the loop with finance', 'domain': 'board_packs', 'hint': 'Close the loop with finance for Board Packs before the shift ends.'},
    {'step': 9, 'title': 'File the audit crumb', 'domain': 'board_packs', 'hint': 'File the audit crumb for Board Packs before the shift ends.'},
    {'step': 10, 'title': 'Schedule the next review', 'domain': 'board_packs', 'hint': 'Schedule the next review for Board Packs before the shift ends.'},
]


def board_packs_playbook() -> list[dict[str, Any]]:
    return list(PLAYBOOK_BOARD_PACKS)


def board_packs_exception_needed(row: dict[str, Any]) -> bool:
    return board_packs_risk_band(row) in ('elevated', 'critical')


def board_packs_freeze_window(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    return status in ['frozen', 'sent'] and date.today().weekday() >= 5


def board_packs_summary_line(row: dict[str, Any]) -> str:
    ident = str(row.get('id') or 'new')
    status = str(row.get('status') or 'n/a')
    band = board_packs_risk_band(row)
    return DOMAIN_TITLE + ' ' + ident + ' is ' + status + ' (' + band + ').'

def board_packs_check_pack_code(value: Any) -> list[str]:
    """Field policy for Pack Code inside Board Packs."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Pack Code is required on Board Packs.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Pack Code is zero; confirm the Board Packs case.')
        if number > 9_000_000_000:
            notes.append('Pack Code exceeds the Board Packs ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Pack Code must be YYYY-MM-DD for Board Packs.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Pack Code is longer than the Board Packs ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Pack Code placeholder values are not allowed on Board Packs.')
    return notes


def board_packs_normalize_pack_code(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def board_packs_describe_pack_code() -> str:
    required = 'required' if True else 'optional'
    return 'Pack Code is a ' + required + ' str field on Board Packs (board_packs).'


def board_packs_check_meeting_on(value: Any) -> list[str]:
    """Field policy for Meeting On inside Board Packs."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Meeting On is required on Board Packs.')
        return notes
    if 'date' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Meeting On is zero; confirm the Board Packs case.')
        if number > 9_000_000_000:
            notes.append('Meeting On exceeds the Board Packs ceiling.')
        return notes
    if 'date' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Meeting On must be YYYY-MM-DD for Board Packs.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Meeting On is longer than the Board Packs ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Meeting On placeholder values are not allowed on Board Packs.')
    return notes


def board_packs_normalize_meeting_on(value: Any) -> Any:
    if 'date' == 'int':
        return _as_int(value)
    if 'date' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def board_packs_describe_meeting_on() -> str:
    required = 'required' if True else 'optional'
    return 'Meeting On is a ' + required + ' date field on Board Packs (board_packs).'


def board_packs_check_owner(value: Any) -> list[str]:
    """Field policy for Owner inside Board Packs."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Owner is required on Board Packs.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Owner is zero; confirm the Board Packs case.')
        if number > 9_000_000_000:
            notes.append('Owner exceeds the Board Packs ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Owner must be YYYY-MM-DD for Board Packs.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Owner is longer than the Board Packs ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Owner placeholder values are not allowed on Board Packs.')
    return notes


def board_packs_normalize_owner(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def board_packs_describe_owner() -> str:
    required = 'required' if True else 'optional'
    return 'Owner is a ' + required + ' str field on Board Packs (board_packs).'


def board_packs_check_page_count(value: Any) -> list[str]:
    """Field policy for Page Count inside Board Packs."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Page Count is required on Board Packs.')
        return notes
    if 'int' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Page Count is zero; confirm the Board Packs case.')
        if number > 9_000_000_000:
            notes.append('Page Count exceeds the Board Packs ceiling.')
        return notes
    if 'int' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Page Count must be YYYY-MM-DD for Board Packs.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Page Count is longer than the Board Packs ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Page Count placeholder values are not allowed on Board Packs.')
    return notes


def board_packs_normalize_page_count(value: Any) -> Any:
    if 'int' == 'int':
        return _as_int(value)
    if 'int' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def board_packs_describe_page_count() -> str:
    required = 'required' if True else 'optional'
    return 'Page Count is a ' + required + ' int field on Board Packs (board_packs).'


def board_packs_check_status(value: Any) -> list[str]:
    """Field policy for Status inside Board Packs."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Status is required on Board Packs.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Status is zero; confirm the Board Packs case.')
        if number > 9_000_000_000:
            notes.append('Status exceeds the Board Packs ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Status must be YYYY-MM-DD for Board Packs.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Status is longer than the Board Packs ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Status placeholder values are not allowed on Board Packs.')
    return notes


def board_packs_normalize_status(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def board_packs_describe_status() -> str:
    required = 'required' if True else 'optional'
    return 'Status is a ' + required + ' str field on Board Packs (board_packs).'


FIELD_CHECKS_BOARD_PACKS = {
    'pack_code': board_packs_check_pack_code,
    'meeting_on': board_packs_check_meeting_on,
    'owner': board_packs_check_owner,
    'page_count': board_packs_check_page_count,
    'status': board_packs_check_status,
}


def board_packs_run_field_checks(row: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for name, checker in FIELD_CHECKS_BOARD_PACKS.items():
        found.extend(checker(row.get(name)))
    return found


def board_packs_policy_card(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'domain': DOMAIN_KEY,
        'title': DOMAIN_TITLE,
        'band': board_packs_risk_band(row),
        'owner': board_packs_owner_hint(row),
        'sla_hours': board_packs_sla_hours(row),
        'exceptions': board_packs_exception_needed(row),
        'freeze': board_packs_freeze_window(row),
        'violations': policy.collect(row) + board_packs_run_field_checks(row),
        'summary': board_packs_summary_line(row),
    }

