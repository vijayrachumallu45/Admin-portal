"""Policy engine for Quote Workshop.

Commercial offers with discount governance.
Operators use these guards before a write is allowed to settle.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

DOMAIN_KEY = 'quotes'
DOMAIN_TITLE = 'Quote Workshop'
ACCENT = '#fcd34d'
STATUSES = ['draft', 'sent', 'accepted', 'expired']
SOFT_HOLD_STATUSES = ['accepted', 'expired']


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ''):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def quotes_policy_version() -> str:
    return 'quotes.policy.4'


def quotes_is_terminal(status: str) -> bool:
    return status == 'expired'


def quotes_requires_dual_control(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status in SOFT_HOLD_STATUSES:
        return True
    score = _as_int(row.get('health_score'))
    return score < 35


class QuotesPolicy:
    """Named checks that finance, people, and platform leads can quote."""

    def __init__(self) -> None:
        self.domain = 'quotes'
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
            self.violations.append('Quote Workshop: status is missing.')
            return
        if status not in STATUSES:
            self.violations.append('Quote Workshop: status is outside the published ladder.')

    def check_identity(self, row: dict[str, Any]) -> None:
        record_id = str(row.get('id') or '')
        if record_id and ' ' in record_id:
            self.violations.append('Quote Workshop: record id cannot contain spaces.')

    def check_freshness(self, row: dict[str, Any]) -> None:
        stamp = str(row.get('updated_at') or '')
        if not stamp:
            return
        try:
            parsed = datetime.fromisoformat(stamp.replace('Z', ''))
        except ValueError:
            self.violations.append('Quote Workshop: updated_at is not parseable.')
            return
        age = (datetime.utcnow() - parsed).days
        if age > 800:
            self.violations.append('Quote Workshop: record is older than the archive window.')

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
                self.violations.append('Quote Workshop: ' + name + ' is out of bounds.')

    def check_text_hygiene(self, row: dict[str, Any]) -> None:
        for name, value in row.items():
            if not isinstance(value, str):
                continue
            if '\x00' in value:
                self.violations.append('Quote Workshop: ' + name + ' contains a null byte.')
            if value != value.strip() and name not in ('comment',):
                self.violations.append('Quote Workshop: ' + name + ' has surrounding whitespace.')

    def check_lifecycle(self, row: dict[str, Any]) -> None:
        status = str(row.get('status') or '')
        if status == 'expired' and _as_int(row.get('health_score')) > 90:
            self.violations.append('Quote Workshop: terminal status with a high health score needs a note.')

    def allow_write(self, row: dict[str, Any]) -> bool:
        return not self.collect(row)


policy = QuotesPolicy()


def quotes_gate_create(payload: dict[str, Any]) -> list[str]:
    return policy.collect(payload)


def quotes_gate_transition(current: str, nxt: str) -> list[str]:
    errors: list[str] = []
    if nxt not in STATUSES:
        errors.append('Quote Workshop cannot move to an unknown status.')
    if current == 'expired' and nxt != current:
        if nxt not in STATUSES[:1]:
            errors.append('Quote Workshop is sealed; only a reopen to the first status is modeled.')
    return errors


def quotes_risk_band(row: dict[str, Any]) -> str:
    score = _as_int(row.get('health_score'))
    if score >= 80:
        return 'calm'
    if score >= 55:
        return 'watch'
    if score >= 30:
        return 'elevated'
    return 'critical'


def quotes_owner_hint(row: dict[str, Any]) -> str:
    for candidate in ('owner', 'assignee', 'steward', 'manager', 'legal_owner', 'processor', 'host_name', 'sponsor'):
        value = str(row.get(candidate) or '').strip()
        if value:
            return value
    return 'unassigned-quotes'


def quotes_sla_hours(row: dict[str, Any]) -> int:
    band = quotes_risk_band(row)
    mapping = {'calm': 72, 'watch': 36, 'elevated': 12, 'critical': 4}
    return mapping[band]


def quotes_escalation_copy(row: dict[str, Any]) -> str:
    band = quotes_risk_band(row)
    owner = quotes_owner_hint(row)
    hours = quotes_sla_hours(row)
    return DOMAIN_TITLE + ' ' + band + ' item assigned to ' + owner + ' must move within ' + str(hours) + ' hours.'


PLAYBOOK_QUOTES = [
    {'step': 1, 'title': 'Triage', 'domain': 'quotes', 'hint': 'Triage for Quote Workshop before the shift ends.'},
    {'step': 2, 'title': 'Confirm identifiers', 'domain': 'quotes', 'hint': 'Confirm identifiers for Quote Workshop before the shift ends.'},
    {'step': 3, 'title': 'Check policy exceptions', 'domain': 'quotes', 'hint': 'Check policy exceptions for Quote Workshop before the shift ends.'},
    {'step': 4, 'title': 'Notify the owner', 'domain': 'quotes', 'hint': 'Notify the owner for Quote Workshop before the shift ends.'},
    {'step': 5, 'title': 'Capture evidence', 'domain': 'quotes', 'hint': 'Capture evidence for Quote Workshop before the shift ends.'},
    {'step': 6, 'title': 'Propose a next status', 'domain': 'quotes', 'hint': 'Propose a next status for Quote Workshop before the shift ends.'},
    {'step': 7, 'title': 'Record the decision', 'domain': 'quotes', 'hint': 'Record the decision for Quote Workshop before the shift ends.'},
    {'step': 8, 'title': 'Close the loop with finance', 'domain': 'quotes', 'hint': 'Close the loop with finance for Quote Workshop before the shift ends.'},
    {'step': 9, 'title': 'File the audit crumb', 'domain': 'quotes', 'hint': 'File the audit crumb for Quote Workshop before the shift ends.'},
    {'step': 10, 'title': 'Schedule the next review', 'domain': 'quotes', 'hint': 'Schedule the next review for Quote Workshop before the shift ends.'},
]


def quotes_playbook() -> list[dict[str, Any]]:
    return list(PLAYBOOK_QUOTES)


def quotes_exception_needed(row: dict[str, Any]) -> bool:
    return quotes_risk_band(row) in ('elevated', 'critical')


def quotes_freeze_window(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    return status in ['accepted', 'expired'] and date.today().weekday() >= 5


def quotes_summary_line(row: dict[str, Any]) -> str:
    ident = str(row.get('id') or 'new')
    status = str(row.get('status') or 'n/a')
    band = quotes_risk_band(row)
    return DOMAIN_TITLE + ' ' + ident + ' is ' + status + ' (' + band + ').'

def quotes_check_quote_no(value: Any) -> list[str]:
    """Field policy for Quote No inside Quote Workshop."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Quote No is required on Quote Workshop.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Quote No is zero; confirm the Quote Workshop case.')
        if number > 9_000_000_000:
            notes.append('Quote No exceeds the Quote Workshop ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Quote No must be YYYY-MM-DD for Quote Workshop.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Quote No is longer than the Quote Workshop ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Quote No placeholder values are not allowed on Quote Workshop.')
    return notes


def quotes_normalize_quote_no(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def quotes_describe_quote_no() -> str:
    required = 'required' if True else 'optional'
    return 'Quote No is a ' + required + ' str field on Quote Workshop (quotes).'


def quotes_check_account_name(value: Any) -> list[str]:
    """Field policy for Account Name inside Quote Workshop."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Account Name is required on Quote Workshop.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Account Name is zero; confirm the Quote Workshop case.')
        if number > 9_000_000_000:
            notes.append('Account Name exceeds the Quote Workshop ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Account Name must be YYYY-MM-DD for Quote Workshop.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Account Name is longer than the Quote Workshop ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Account Name placeholder values are not allowed on Quote Workshop.')
    return notes


def quotes_normalize_account_name(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def quotes_describe_account_name() -> str:
    required = 'required' if True else 'optional'
    return 'Account Name is a ' + required + ' str field on Quote Workshop (quotes).'


def quotes_check_list_cents(value: Any) -> list[str]:
    """Field policy for List Cents inside Quote Workshop."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('List Cents is required on Quote Workshop.')
        return notes
    if 'int' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('List Cents is zero; confirm the Quote Workshop case.')
        if number > 9_000_000_000:
            notes.append('List Cents exceeds the Quote Workshop ceiling.')
        return notes
    if 'int' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('List Cents must be YYYY-MM-DD for Quote Workshop.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('List Cents is longer than the Quote Workshop ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('List Cents placeholder values are not allowed on Quote Workshop.')
    return notes


def quotes_normalize_list_cents(value: Any) -> Any:
    if 'int' == 'int':
        return _as_int(value)
    if 'int' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def quotes_describe_list_cents() -> str:
    required = 'required' if True else 'optional'
    return 'List Cents is a ' + required + ' int field on Quote Workshop (quotes).'


def quotes_check_discount_bps(value: Any) -> list[str]:
    """Field policy for Discount Bps inside Quote Workshop."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Discount Bps is required on Quote Workshop.')
        return notes
    if 'int' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Discount Bps is zero; confirm the Quote Workshop case.')
        if number > 9_000_000_000:
            notes.append('Discount Bps exceeds the Quote Workshop ceiling.')
        return notes
    if 'int' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Discount Bps must be YYYY-MM-DD for Quote Workshop.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Discount Bps is longer than the Quote Workshop ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Discount Bps placeholder values are not allowed on Quote Workshop.')
    return notes


def quotes_normalize_discount_bps(value: Any) -> Any:
    if 'int' == 'int':
        return _as_int(value)
    if 'int' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def quotes_describe_discount_bps() -> str:
    required = 'required' if True else 'optional'
    return 'Discount Bps is a ' + required + ' int field on Quote Workshop (quotes).'


def quotes_check_owner(value: Any) -> list[str]:
    """Field policy for Owner inside Quote Workshop."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Owner is required on Quote Workshop.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Owner is zero; confirm the Quote Workshop case.')
        if number > 9_000_000_000:
            notes.append('Owner exceeds the Quote Workshop ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Owner must be YYYY-MM-DD for Quote Workshop.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Owner is longer than the Quote Workshop ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Owner placeholder values are not allowed on Quote Workshop.')
    return notes


def quotes_normalize_owner(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def quotes_describe_owner() -> str:
    required = 'required' if True else 'optional'
    return 'Owner is a ' + required + ' str field on Quote Workshop (quotes).'


def quotes_check_status(value: Any) -> list[str]:
    """Field policy for Status inside Quote Workshop."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Status is required on Quote Workshop.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Status is zero; confirm the Quote Workshop case.')
        if number > 9_000_000_000:
            notes.append('Status exceeds the Quote Workshop ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Status must be YYYY-MM-DD for Quote Workshop.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Status is longer than the Quote Workshop ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Status placeholder values are not allowed on Quote Workshop.')
    return notes


def quotes_normalize_status(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def quotes_describe_status() -> str:
    required = 'required' if True else 'optional'
    return 'Status is a ' + required + ' str field on Quote Workshop (quotes).'


FIELD_CHECKS_QUOTES = {
    'quote_no': quotes_check_quote_no,
    'account_name': quotes_check_account_name,
    'list_cents': quotes_check_list_cents,
    'discount_bps': quotes_check_discount_bps,
    'owner': quotes_check_owner,
    'status': quotes_check_status,
}


def quotes_run_field_checks(row: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for name, checker in FIELD_CHECKS_QUOTES.items():
        found.extend(checker(row.get(name)))
    return found


def quotes_policy_card(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'domain': DOMAIN_KEY,
        'title': DOMAIN_TITLE,
        'band': quotes_risk_band(row),
        'owner': quotes_owner_hint(row),
        'sla_hours': quotes_sla_hours(row),
        'exceptions': quotes_exception_needed(row),
        'freeze': quotes_freeze_window(row),
        'violations': policy.collect(row) + quotes_run_field_checks(row),
        'summary': quotes_summary_line(row),
    }

