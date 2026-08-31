"""Policy engine for Price Books.

Regional price books and currency schedules.
Operators use these guards before a write is allowed to settle.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

DOMAIN_KEY = 'price_books'
DOMAIN_TITLE = 'Price Books'
ACCENT = '#fde047'
STATUSES = ['draft', 'active', 'superseded']
SOFT_HOLD_STATUSES = ['active', 'superseded']


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ''):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def price_books_policy_version() -> str:
    return 'price_books.policy.4'


def price_books_is_terminal(status: str) -> bool:
    return status == 'superseded'


def price_books_requires_dual_control(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status in SOFT_HOLD_STATUSES:
        return True
    score = _as_int(row.get('health_score'))
    return score < 35


class PriceBooksPolicy:
    """Named checks that finance, people, and platform leads can quote."""

    def __init__(self) -> None:
        self.domain = 'price_books'
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
            self.violations.append('Price Books: status is missing.')
            return
        if status not in STATUSES:
            self.violations.append('Price Books: status is outside the published ladder.')

    def check_identity(self, row: dict[str, Any]) -> None:
        record_id = str(row.get('id') or '')
        if record_id and ' ' in record_id:
            self.violations.append('Price Books: record id cannot contain spaces.')

    def check_freshness(self, row: dict[str, Any]) -> None:
        stamp = str(row.get('updated_at') or '')
        if not stamp:
            return
        try:
            parsed = datetime.fromisoformat(stamp.replace('Z', ''))
        except ValueError:
            self.violations.append('Price Books: updated_at is not parseable.')
            return
        age = (datetime.utcnow() - parsed).days
        if age > 800:
            self.violations.append('Price Books: record is older than the archive window.')

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
                self.violations.append('Price Books: ' + name + ' is out of bounds.')

    def check_text_hygiene(self, row: dict[str, Any]) -> None:
        for name, value in row.items():
            if not isinstance(value, str):
                continue
            if '\x00' in value:
                self.violations.append('Price Books: ' + name + ' contains a null byte.')
            if value != value.strip() and name not in ('comment',):
                self.violations.append('Price Books: ' + name + ' has surrounding whitespace.')

    def check_lifecycle(self, row: dict[str, Any]) -> None:
        status = str(row.get('status') or '')
        if status == 'superseded' and _as_int(row.get('health_score')) > 90:
            self.violations.append('Price Books: terminal status with a high health score needs a note.')

    def allow_write(self, row: dict[str, Any]) -> bool:
        return not self.collect(row)


policy = PriceBooksPolicy()


def price_books_gate_create(payload: dict[str, Any]) -> list[str]:
    return policy.collect(payload)


def price_books_gate_transition(current: str, nxt: str) -> list[str]:
    errors: list[str] = []
    if nxt not in STATUSES:
        errors.append('Price Books cannot move to an unknown status.')
    if current == 'superseded' and nxt != current:
        if nxt not in STATUSES[:1]:
            errors.append('Price Books is sealed; only a reopen to the first status is modeled.')
    return errors


def price_books_risk_band(row: dict[str, Any]) -> str:
    score = _as_int(row.get('health_score'))
    if score >= 80:
        return 'calm'
    if score >= 55:
        return 'watch'
    if score >= 30:
        return 'elevated'
    return 'critical'


def price_books_owner_hint(row: dict[str, Any]) -> str:
    for candidate in ('owner', 'assignee', 'steward', 'manager', 'legal_owner', 'processor', 'host_name', 'sponsor'):
        value = str(row.get(candidate) or '').strip()
        if value:
            return value
    return 'unassigned-price_books'


def price_books_sla_hours(row: dict[str, Any]) -> int:
    band = price_books_risk_band(row)
    mapping = {'calm': 72, 'watch': 36, 'elevated': 12, 'critical': 4}
    return mapping[band]


def price_books_escalation_copy(row: dict[str, Any]) -> str:
    band = price_books_risk_band(row)
    owner = price_books_owner_hint(row)
    hours = price_books_sla_hours(row)
    return DOMAIN_TITLE + ' ' + band + ' item assigned to ' + owner + ' must move within ' + str(hours) + ' hours.'


PLAYBOOK_PRICE_BOOKS = [
    {'step': 1, 'title': 'Triage', 'domain': 'price_books', 'hint': 'Triage for Price Books before the shift ends.'},
    {'step': 2, 'title': 'Confirm identifiers', 'domain': 'price_books', 'hint': 'Confirm identifiers for Price Books before the shift ends.'},
    {'step': 3, 'title': 'Check policy exceptions', 'domain': 'price_books', 'hint': 'Check policy exceptions for Price Books before the shift ends.'},
    {'step': 4, 'title': 'Notify the owner', 'domain': 'price_books', 'hint': 'Notify the owner for Price Books before the shift ends.'},
    {'step': 5, 'title': 'Capture evidence', 'domain': 'price_books', 'hint': 'Capture evidence for Price Books before the shift ends.'},
    {'step': 6, 'title': 'Propose a next status', 'domain': 'price_books', 'hint': 'Propose a next status for Price Books before the shift ends.'},
    {'step': 7, 'title': 'Record the decision', 'domain': 'price_books', 'hint': 'Record the decision for Price Books before the shift ends.'},
    {'step': 8, 'title': 'Close the loop with finance', 'domain': 'price_books', 'hint': 'Close the loop with finance for Price Books before the shift ends.'},
    {'step': 9, 'title': 'File the audit crumb', 'domain': 'price_books', 'hint': 'File the audit crumb for Price Books before the shift ends.'},
    {'step': 10, 'title': 'Schedule the next review', 'domain': 'price_books', 'hint': 'Schedule the next review for Price Books before the shift ends.'},
]


def price_books_playbook() -> list[dict[str, Any]]:
    return list(PLAYBOOK_PRICE_BOOKS)


def price_books_exception_needed(row: dict[str, Any]) -> bool:
    return price_books_risk_band(row) in ('elevated', 'critical')


def price_books_freeze_window(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    return status in ['active', 'superseded'] and date.today().weekday() >= 5


def price_books_summary_line(row: dict[str, Any]) -> str:
    ident = str(row.get('id') or 'new')
    status = str(row.get('status') or 'n/a')
    band = price_books_risk_band(row)
    return DOMAIN_TITLE + ' ' + ident + ' is ' + status + ' (' + band + ').'

def price_books_check_book_code(value: Any) -> list[str]:
    """Field policy for Book Code inside Price Books."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Book Code is required on Price Books.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Book Code is zero; confirm the Price Books case.')
        if number > 9_000_000_000:
            notes.append('Book Code exceeds the Price Books ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Book Code must be YYYY-MM-DD for Price Books.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Book Code is longer than the Price Books ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Book Code placeholder values are not allowed on Price Books.')
    return notes


def price_books_normalize_book_code(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def price_books_describe_book_code() -> str:
    required = 'required' if True else 'optional'
    return 'Book Code is a ' + required + ' str field on Price Books (price_books).'


def price_books_check_region(value: Any) -> list[str]:
    """Field policy for Region inside Price Books."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Region is required on Price Books.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Region is zero; confirm the Price Books case.')
        if number > 9_000_000_000:
            notes.append('Region exceeds the Price Books ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Region must be YYYY-MM-DD for Price Books.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Region is longer than the Price Books ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Region placeholder values are not allowed on Price Books.')
    return notes


def price_books_normalize_region(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def price_books_describe_region() -> str:
    required = 'required' if True else 'optional'
    return 'Region is a ' + required + ' str field on Price Books (price_books).'


def price_books_check_currency(value: Any) -> list[str]:
    """Field policy for Currency inside Price Books."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Currency is required on Price Books.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Currency is zero; confirm the Price Books case.')
        if number > 9_000_000_000:
            notes.append('Currency exceeds the Price Books ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Currency must be YYYY-MM-DD for Price Books.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Currency is longer than the Price Books ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Currency placeholder values are not allowed on Price Books.')
    return notes


def price_books_normalize_currency(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def price_books_describe_currency() -> str:
    required = 'required' if True else 'optional'
    return 'Currency is a ' + required + ' str field on Price Books (price_books).'


def price_books_check_valid_from(value: Any) -> list[str]:
    """Field policy for Valid From inside Price Books."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Valid From is required on Price Books.')
        return notes
    if 'date' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Valid From is zero; confirm the Price Books case.')
        if number > 9_000_000_000:
            notes.append('Valid From exceeds the Price Books ceiling.')
        return notes
    if 'date' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Valid From must be YYYY-MM-DD for Price Books.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Valid From is longer than the Price Books ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Valid From placeholder values are not allowed on Price Books.')
    return notes


def price_books_normalize_valid_from(value: Any) -> Any:
    if 'date' == 'int':
        return _as_int(value)
    if 'date' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def price_books_describe_valid_from() -> str:
    required = 'required' if True else 'optional'
    return 'Valid From is a ' + required + ' date field on Price Books (price_books).'


def price_books_check_status(value: Any) -> list[str]:
    """Field policy for Status inside Price Books."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Status is required on Price Books.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Status is zero; confirm the Price Books case.')
        if number > 9_000_000_000:
            notes.append('Status exceeds the Price Books ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Status must be YYYY-MM-DD for Price Books.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Status is longer than the Price Books ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Status placeholder values are not allowed on Price Books.')
    return notes


def price_books_normalize_status(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def price_books_describe_status() -> str:
    required = 'required' if True else 'optional'
    return 'Status is a ' + required + ' str field on Price Books (price_books).'


FIELD_CHECKS_PRICE_BOOKS = {
    'book_code': price_books_check_book_code,
    'region': price_books_check_region,
    'currency': price_books_check_currency,
    'valid_from': price_books_check_valid_from,
    'status': price_books_check_status,
}


def price_books_run_field_checks(row: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for name, checker in FIELD_CHECKS_PRICE_BOOKS.items():
        found.extend(checker(row.get(name)))
    return found


def price_books_policy_card(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'domain': DOMAIN_KEY,
        'title': DOMAIN_TITLE,
        'band': price_books_risk_band(row),
        'owner': price_books_owner_hint(row),
        'sla_hours': price_books_sla_hours(row),
        'exceptions': price_books_exception_needed(row),
        'freeze': price_books_freeze_window(row),
        'violations': policy.collect(row) + price_books_run_field_checks(row),
        'summary': price_books_summary_line(row),
    }

