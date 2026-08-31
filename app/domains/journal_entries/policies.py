"""Policy engine for Journal Entries.

Manual ledger posts awaiting controller review.
Operators use these guards before a write is allowed to settle.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

DOMAIN_KEY = 'journal_entries'
DOMAIN_TITLE = 'Journal Entries'
ACCENT = '#94a3b8'
STATUSES = ['draft', 'posted', 'reversed']
SOFT_HOLD_STATUSES = ['posted', 'reversed']


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ''):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def journal_entries_policy_version() -> str:
    return 'journal_entries.policy.4'


def journal_entries_is_terminal(status: str) -> bool:
    return status == 'reversed'


def journal_entries_requires_dual_control(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status in SOFT_HOLD_STATUSES:
        return True
    score = _as_int(row.get('health_score'))
    return score < 35


class JournalEntriesPolicy:
    """Named checks that finance, people, and platform leads can quote."""

    def __init__(self) -> None:
        self.domain = 'journal_entries'
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
            self.violations.append('Journal Entries: status is missing.')
            return
        if status not in STATUSES:
            self.violations.append('Journal Entries: status is outside the published ladder.')

    def check_identity(self, row: dict[str, Any]) -> None:
        record_id = str(row.get('id') or '')
        if record_id and ' ' in record_id:
            self.violations.append('Journal Entries: record id cannot contain spaces.')

    def check_freshness(self, row: dict[str, Any]) -> None:
        stamp = str(row.get('updated_at') or '')
        if not stamp:
            return
        try:
            parsed = datetime.fromisoformat(stamp.replace('Z', ''))
        except ValueError:
            self.violations.append('Journal Entries: updated_at is not parseable.')
            return
        age = (datetime.utcnow() - parsed).days
        if age > 800:
            self.violations.append('Journal Entries: record is older than the archive window.')

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
                self.violations.append('Journal Entries: ' + name + ' is out of bounds.')

    def check_text_hygiene(self, row: dict[str, Any]) -> None:
        for name, value in row.items():
            if not isinstance(value, str):
                continue
            if '\x00' in value:
                self.violations.append('Journal Entries: ' + name + ' contains a null byte.')
            if value != value.strip() and name not in ('comment',):
                self.violations.append('Journal Entries: ' + name + ' has surrounding whitespace.')

    def check_lifecycle(self, row: dict[str, Any]) -> None:
        status = str(row.get('status') or '')
        if status == 'reversed' and _as_int(row.get('health_score')) > 90:
            self.violations.append('Journal Entries: terminal status with a high health score needs a note.')

    def allow_write(self, row: dict[str, Any]) -> bool:
        return not self.collect(row)


policy = JournalEntriesPolicy()


def journal_entries_gate_create(payload: dict[str, Any]) -> list[str]:
    return policy.collect(payload)


def journal_entries_gate_transition(current: str, nxt: str) -> list[str]:
    errors: list[str] = []
    if nxt not in STATUSES:
        errors.append('Journal Entries cannot move to an unknown status.')
    if current == 'reversed' and nxt != current:
        if nxt not in STATUSES[:1]:
            errors.append('Journal Entries is sealed; only a reopen to the first status is modeled.')
    return errors


def journal_entries_risk_band(row: dict[str, Any]) -> str:
    score = _as_int(row.get('health_score'))
    if score >= 80:
        return 'calm'
    if score >= 55:
        return 'watch'
    if score >= 30:
        return 'elevated'
    return 'critical'


def journal_entries_owner_hint(row: dict[str, Any]) -> str:
    for candidate in ('owner', 'assignee', 'steward', 'manager', 'legal_owner', 'processor', 'host_name', 'sponsor'):
        value = str(row.get(candidate) or '').strip()
        if value:
            return value
    return 'unassigned-journal_entries'


def journal_entries_sla_hours(row: dict[str, Any]) -> int:
    band = journal_entries_risk_band(row)
    mapping = {'calm': 72, 'watch': 36, 'elevated': 12, 'critical': 4}
    return mapping[band]


def journal_entries_escalation_copy(row: dict[str, Any]) -> str:
    band = journal_entries_risk_band(row)
    owner = journal_entries_owner_hint(row)
    hours = journal_entries_sla_hours(row)
    return DOMAIN_TITLE + ' ' + band + ' item assigned to ' + owner + ' must move within ' + str(hours) + ' hours.'


PLAYBOOK_JOURNAL_ENTRIES = [
    {'step': 1, 'title': 'Triage', 'domain': 'journal_entries', 'hint': 'Triage for Journal Entries before the shift ends.'},
    {'step': 2, 'title': 'Confirm identifiers', 'domain': 'journal_entries', 'hint': 'Confirm identifiers for Journal Entries before the shift ends.'},
    {'step': 3, 'title': 'Check policy exceptions', 'domain': 'journal_entries', 'hint': 'Check policy exceptions for Journal Entries before the shift ends.'},
    {'step': 4, 'title': 'Notify the owner', 'domain': 'journal_entries', 'hint': 'Notify the owner for Journal Entries before the shift ends.'},
    {'step': 5, 'title': 'Capture evidence', 'domain': 'journal_entries', 'hint': 'Capture evidence for Journal Entries before the shift ends.'},
    {'step': 6, 'title': 'Propose a next status', 'domain': 'journal_entries', 'hint': 'Propose a next status for Journal Entries before the shift ends.'},
    {'step': 7, 'title': 'Record the decision', 'domain': 'journal_entries', 'hint': 'Record the decision for Journal Entries before the shift ends.'},
    {'step': 8, 'title': 'Close the loop with finance', 'domain': 'journal_entries', 'hint': 'Close the loop with finance for Journal Entries before the shift ends.'},
    {'step': 9, 'title': 'File the audit crumb', 'domain': 'journal_entries', 'hint': 'File the audit crumb for Journal Entries before the shift ends.'},
    {'step': 10, 'title': 'Schedule the next review', 'domain': 'journal_entries', 'hint': 'Schedule the next review for Journal Entries before the shift ends.'},
]


def journal_entries_playbook() -> list[dict[str, Any]]:
    return list(PLAYBOOK_JOURNAL_ENTRIES)


def journal_entries_exception_needed(row: dict[str, Any]) -> bool:
    return journal_entries_risk_band(row) in ('elevated', 'critical')


def journal_entries_freeze_window(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    return status in ['posted', 'reversed'] and date.today().weekday() >= 5


def journal_entries_summary_line(row: dict[str, Any]) -> str:
    ident = str(row.get('id') or 'new')
    status = str(row.get('status') or 'n/a')
    band = journal_entries_risk_band(row)
    return DOMAIN_TITLE + ' ' + ident + ' is ' + status + ' (' + band + ').'

def journal_entries_check_entry_no(value: Any) -> list[str]:
    """Field policy for Entry No inside Journal Entries."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Entry No is required on Journal Entries.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Entry No is zero; confirm the Journal Entries case.')
        if number > 9_000_000_000:
            notes.append('Entry No exceeds the Journal Entries ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Entry No must be YYYY-MM-DD for Journal Entries.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Entry No is longer than the Journal Entries ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Entry No placeholder values are not allowed on Journal Entries.')
    return notes


def journal_entries_normalize_entry_no(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def journal_entries_describe_entry_no() -> str:
    required = 'required' if True else 'optional'
    return 'Entry No is a ' + required + ' str field on Journal Entries (journal_entries).'


def journal_entries_check_memo(value: Any) -> list[str]:
    """Field policy for Memo inside Journal Entries."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Memo is required on Journal Entries.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Memo is zero; confirm the Journal Entries case.')
        if number > 9_000_000_000:
            notes.append('Memo exceeds the Journal Entries ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Memo must be YYYY-MM-DD for Journal Entries.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Memo is longer than the Journal Entries ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Memo placeholder values are not allowed on Journal Entries.')
    return notes


def journal_entries_normalize_memo(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def journal_entries_describe_memo() -> str:
    required = 'required' if True else 'optional'
    return 'Memo is a ' + required + ' str field on Journal Entries (journal_entries).'


def journal_entries_check_amount_cents(value: Any) -> list[str]:
    """Field policy for Amount Cents inside Journal Entries."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Amount Cents is required on Journal Entries.')
        return notes
    if 'int' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Amount Cents is zero; confirm the Journal Entries case.')
        if number > 9_000_000_000:
            notes.append('Amount Cents exceeds the Journal Entries ceiling.')
        return notes
    if 'int' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Amount Cents must be YYYY-MM-DD for Journal Entries.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Amount Cents is longer than the Journal Entries ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Amount Cents placeholder values are not allowed on Journal Entries.')
    return notes


def journal_entries_normalize_amount_cents(value: Any) -> Any:
    if 'int' == 'int':
        return _as_int(value)
    if 'int' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def journal_entries_describe_amount_cents() -> str:
    required = 'required' if True else 'optional'
    return 'Amount Cents is a ' + required + ' int field on Journal Entries (journal_entries).'


def journal_entries_check_posted_on(value: Any) -> list[str]:
    """Field policy for Posted On inside Journal Entries."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Posted On is required on Journal Entries.')
        return notes
    if 'date' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Posted On is zero; confirm the Journal Entries case.')
        if number > 9_000_000_000:
            notes.append('Posted On exceeds the Journal Entries ceiling.')
        return notes
    if 'date' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Posted On must be YYYY-MM-DD for Journal Entries.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Posted On is longer than the Journal Entries ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Posted On placeholder values are not allowed on Journal Entries.')
    return notes


def journal_entries_normalize_posted_on(value: Any) -> Any:
    if 'date' == 'int':
        return _as_int(value)
    if 'date' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def journal_entries_describe_posted_on() -> str:
    required = 'required' if True else 'optional'
    return 'Posted On is a ' + required + ' date field on Journal Entries (journal_entries).'


def journal_entries_check_status(value: Any) -> list[str]:
    """Field policy for Status inside Journal Entries."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Status is required on Journal Entries.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Status is zero; confirm the Journal Entries case.')
        if number > 9_000_000_000:
            notes.append('Status exceeds the Journal Entries ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Status must be YYYY-MM-DD for Journal Entries.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Status is longer than the Journal Entries ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Status placeholder values are not allowed on Journal Entries.')
    return notes


def journal_entries_normalize_status(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def journal_entries_describe_status() -> str:
    required = 'required' if True else 'optional'
    return 'Status is a ' + required + ' str field on Journal Entries (journal_entries).'


FIELD_CHECKS_JOURNAL_ENTRIES = {
    'entry_no': journal_entries_check_entry_no,
    'memo': journal_entries_check_memo,
    'amount_cents': journal_entries_check_amount_cents,
    'posted_on': journal_entries_check_posted_on,
    'status': journal_entries_check_status,
}


def journal_entries_run_field_checks(row: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for name, checker in FIELD_CHECKS_JOURNAL_ENTRIES.items():
        found.extend(checker(row.get(name)))
    return found


def journal_entries_policy_card(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'domain': DOMAIN_KEY,
        'title': DOMAIN_TITLE,
        'band': journal_entries_risk_band(row),
        'owner': journal_entries_owner_hint(row),
        'sla_hours': journal_entries_sla_hours(row),
        'exceptions': journal_entries_exception_needed(row),
        'freeze': journal_entries_freeze_window(row),
        'violations': policy.collect(row) + journal_entries_run_field_checks(row),
        'summary': journal_entries_summary_line(row),
    }

