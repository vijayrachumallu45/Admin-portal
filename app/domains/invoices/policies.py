"""Policy engine for Invoice Desk.

Accounts receivable documents, collections stages, and aging buckets.
Operators use these guards before a write is allowed to settle.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

DOMAIN_KEY = 'invoices'
DOMAIN_TITLE = 'Invoice Desk'
ACCENT = '#4ade80'
STATUSES = ['draft', 'sent', 'partial', 'paid', 'void']
SOFT_HOLD_STATUSES = ['paid', 'void']


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ''):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def invoices_policy_version() -> str:
    return 'invoices.policy.4'


def invoices_is_terminal(status: str) -> bool:
    return status == 'void'


def invoices_requires_dual_control(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status in SOFT_HOLD_STATUSES:
        return True
    score = _as_int(row.get('health_score'))
    return score < 35


class InvoicesPolicy:
    """Named checks that finance, people, and platform leads can quote."""

    def __init__(self) -> None:
        self.domain = 'invoices'
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
            self.violations.append('Invoice Desk: status is missing.')
            return
        if status not in STATUSES:
            self.violations.append('Invoice Desk: status is outside the published ladder.')

    def check_identity(self, row: dict[str, Any]) -> None:
        record_id = str(row.get('id') or '')
        if record_id and ' ' in record_id:
            self.violations.append('Invoice Desk: record id cannot contain spaces.')

    def check_freshness(self, row: dict[str, Any]) -> None:
        stamp = str(row.get('updated_at') or '')
        if not stamp:
            return
        try:
            parsed = datetime.fromisoformat(stamp.replace('Z', ''))
        except ValueError:
            self.violations.append('Invoice Desk: updated_at is not parseable.')
            return
        age = (datetime.utcnow() - parsed).days
        if age > 800:
            self.violations.append('Invoice Desk: record is older than the archive window.')

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
                self.violations.append('Invoice Desk: ' + name + ' is out of bounds.')

    def check_text_hygiene(self, row: dict[str, Any]) -> None:
        for name, value in row.items():
            if not isinstance(value, str):
                continue
            if '\x00' in value:
                self.violations.append('Invoice Desk: ' + name + ' contains a null byte.')
            if value != value.strip() and name not in ('comment',):
                self.violations.append('Invoice Desk: ' + name + ' has surrounding whitespace.')

    def check_lifecycle(self, row: dict[str, Any]) -> None:
        status = str(row.get('status') or '')
        if status == 'void' and _as_int(row.get('health_score')) > 90:
            self.violations.append('Invoice Desk: terminal status with a high health score needs a note.')

    def allow_write(self, row: dict[str, Any]) -> bool:
        return not self.collect(row)


policy = InvoicesPolicy()


def invoices_gate_create(payload: dict[str, Any]) -> list[str]:
    return policy.collect(payload)


def invoices_gate_transition(current: str, nxt: str) -> list[str]:
    errors: list[str] = []
    if nxt not in STATUSES:
        errors.append('Invoice Desk cannot move to an unknown status.')
    if current == 'void' and nxt != current:
        if nxt not in STATUSES[:1]:
            errors.append('Invoice Desk is sealed; only a reopen to the first status is modeled.')
    return errors


def invoices_risk_band(row: dict[str, Any]) -> str:
    score = _as_int(row.get('health_score'))
    if score >= 80:
        return 'calm'
    if score >= 55:
        return 'watch'
    if score >= 30:
        return 'elevated'
    return 'critical'


def invoices_owner_hint(row: dict[str, Any]) -> str:
    for candidate in ('owner', 'assignee', 'steward', 'manager', 'legal_owner', 'processor', 'host_name', 'sponsor'):
        value = str(row.get(candidate) or '').strip()
        if value:
            return value
    return 'unassigned-invoices'


def invoices_sla_hours(row: dict[str, Any]) -> int:
    band = invoices_risk_band(row)
    mapping = {'calm': 72, 'watch': 36, 'elevated': 12, 'critical': 4}
    return mapping[band]


def invoices_escalation_copy(row: dict[str, Any]) -> str:
    band = invoices_risk_band(row)
    owner = invoices_owner_hint(row)
    hours = invoices_sla_hours(row)
    return DOMAIN_TITLE + ' ' + band + ' item assigned to ' + owner + ' must move within ' + str(hours) + ' hours.'


PLAYBOOK_INVOICES = [
    {'step': 1, 'title': 'Triage', 'domain': 'invoices', 'hint': 'Triage for Invoice Desk before the shift ends.'},
    {'step': 2, 'title': 'Confirm identifiers', 'domain': 'invoices', 'hint': 'Confirm identifiers for Invoice Desk before the shift ends.'},
    {'step': 3, 'title': 'Check policy exceptions', 'domain': 'invoices', 'hint': 'Check policy exceptions for Invoice Desk before the shift ends.'},
    {'step': 4, 'title': 'Notify the owner', 'domain': 'invoices', 'hint': 'Notify the owner for Invoice Desk before the shift ends.'},
    {'step': 5, 'title': 'Capture evidence', 'domain': 'invoices', 'hint': 'Capture evidence for Invoice Desk before the shift ends.'},
    {'step': 6, 'title': 'Propose a next status', 'domain': 'invoices', 'hint': 'Propose a next status for Invoice Desk before the shift ends.'},
    {'step': 7, 'title': 'Record the decision', 'domain': 'invoices', 'hint': 'Record the decision for Invoice Desk before the shift ends.'},
    {'step': 8, 'title': 'Close the loop with finance', 'domain': 'invoices', 'hint': 'Close the loop with finance for Invoice Desk before the shift ends.'},
    {'step': 9, 'title': 'File the audit crumb', 'domain': 'invoices', 'hint': 'File the audit crumb for Invoice Desk before the shift ends.'},
    {'step': 10, 'title': 'Schedule the next review', 'domain': 'invoices', 'hint': 'Schedule the next review for Invoice Desk before the shift ends.'},
]


def invoices_playbook() -> list[dict[str, Any]]:
    return list(PLAYBOOK_INVOICES)


def invoices_exception_needed(row: dict[str, Any]) -> bool:
    return invoices_risk_band(row) in ('elevated', 'critical')


def invoices_freeze_window(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    return status in ['paid', 'void'] and date.today().weekday() >= 5


def invoices_summary_line(row: dict[str, Any]) -> str:
    ident = str(row.get('id') or 'new')
    status = str(row.get('status') or 'n/a')
    band = invoices_risk_band(row)
    return DOMAIN_TITLE + ' ' + ident + ' is ' + status + ' (' + band + ').'

def invoices_check_invoice_no(value: Any) -> list[str]:
    """Field policy for Invoice No inside Invoice Desk."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Invoice No is required on Invoice Desk.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Invoice No is zero; confirm the Invoice Desk case.')
        if number > 9_000_000_000:
            notes.append('Invoice No exceeds the Invoice Desk ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Invoice No must be YYYY-MM-DD for Invoice Desk.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Invoice No is longer than the Invoice Desk ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Invoice No placeholder values are not allowed on Invoice Desk.')
    return notes


def invoices_normalize_invoice_no(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def invoices_describe_invoice_no() -> str:
    required = 'required' if True else 'optional'
    return 'Invoice No is a ' + required + ' str field on Invoice Desk (invoices).'


def invoices_check_customer(value: Any) -> list[str]:
    """Field policy for Customer inside Invoice Desk."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Customer is required on Invoice Desk.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Customer is zero; confirm the Invoice Desk case.')
        if number > 9_000_000_000:
            notes.append('Customer exceeds the Invoice Desk ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Customer must be YYYY-MM-DD for Invoice Desk.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Customer is longer than the Invoice Desk ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Customer placeholder values are not allowed on Invoice Desk.')
    return notes


def invoices_normalize_customer(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def invoices_describe_customer() -> str:
    required = 'required' if True else 'optional'
    return 'Customer is a ' + required + ' str field on Invoice Desk (invoices).'


def invoices_check_amount_cents(value: Any) -> list[str]:
    """Field policy for Amount Cents inside Invoice Desk."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Amount Cents is required on Invoice Desk.')
        return notes
    if 'int' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Amount Cents is zero; confirm the Invoice Desk case.')
        if number > 9_000_000_000:
            notes.append('Amount Cents exceeds the Invoice Desk ceiling.')
        return notes
    if 'int' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Amount Cents must be YYYY-MM-DD for Invoice Desk.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Amount Cents is longer than the Invoice Desk ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Amount Cents placeholder values are not allowed on Invoice Desk.')
    return notes


def invoices_normalize_amount_cents(value: Any) -> Any:
    if 'int' == 'int':
        return _as_int(value)
    if 'int' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def invoices_describe_amount_cents() -> str:
    required = 'required' if True else 'optional'
    return 'Amount Cents is a ' + required + ' int field on Invoice Desk (invoices).'


def invoices_check_currency(value: Any) -> list[str]:
    """Field policy for Currency inside Invoice Desk."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Currency is required on Invoice Desk.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Currency is zero; confirm the Invoice Desk case.')
        if number > 9_000_000_000:
            notes.append('Currency exceeds the Invoice Desk ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Currency must be YYYY-MM-DD for Invoice Desk.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Currency is longer than the Invoice Desk ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Currency placeholder values are not allowed on Invoice Desk.')
    return notes


def invoices_normalize_currency(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def invoices_describe_currency() -> str:
    required = 'required' if True else 'optional'
    return 'Currency is a ' + required + ' str field on Invoice Desk (invoices).'


def invoices_check_issued_on(value: Any) -> list[str]:
    """Field policy for Issued On inside Invoice Desk."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Issued On is required on Invoice Desk.')
        return notes
    if 'date' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Issued On is zero; confirm the Invoice Desk case.')
        if number > 9_000_000_000:
            notes.append('Issued On exceeds the Invoice Desk ceiling.')
        return notes
    if 'date' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Issued On must be YYYY-MM-DD for Invoice Desk.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Issued On is longer than the Invoice Desk ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Issued On placeholder values are not allowed on Invoice Desk.')
    return notes


def invoices_normalize_issued_on(value: Any) -> Any:
    if 'date' == 'int':
        return _as_int(value)
    if 'date' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def invoices_describe_issued_on() -> str:
    required = 'required' if True else 'optional'
    return 'Issued On is a ' + required + ' date field on Invoice Desk (invoices).'


def invoices_check_due_on(value: Any) -> list[str]:
    """Field policy for Due On inside Invoice Desk."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Due On is required on Invoice Desk.')
        return notes
    if 'date' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Due On is zero; confirm the Invoice Desk case.')
        if number > 9_000_000_000:
            notes.append('Due On exceeds the Invoice Desk ceiling.')
        return notes
    if 'date' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Due On must be YYYY-MM-DD for Invoice Desk.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Due On is longer than the Invoice Desk ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Due On placeholder values are not allowed on Invoice Desk.')
    return notes


def invoices_normalize_due_on(value: Any) -> Any:
    if 'date' == 'int':
        return _as_int(value)
    if 'date' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def invoices_describe_due_on() -> str:
    required = 'required' if True else 'optional'
    return 'Due On is a ' + required + ' date field on Invoice Desk (invoices).'


def invoices_check_status(value: Any) -> list[str]:
    """Field policy for Status inside Invoice Desk."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Status is required on Invoice Desk.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Status is zero; confirm the Invoice Desk case.')
        if number > 9_000_000_000:
            notes.append('Status exceeds the Invoice Desk ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Status must be YYYY-MM-DD for Invoice Desk.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Status is longer than the Invoice Desk ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Status placeholder values are not allowed on Invoice Desk.')
    return notes


def invoices_normalize_status(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def invoices_describe_status() -> str:
    required = 'required' if True else 'optional'
    return 'Status is a ' + required + ' str field on Invoice Desk (invoices).'


FIELD_CHECKS_INVOICES = {
    'invoice_no': invoices_check_invoice_no,
    'customer': invoices_check_customer,
    'amount_cents': invoices_check_amount_cents,
    'currency': invoices_check_currency,
    'issued_on': invoices_check_issued_on,
    'due_on': invoices_check_due_on,
    'status': invoices_check_status,
}


def invoices_run_field_checks(row: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for name, checker in FIELD_CHECKS_INVOICES.items():
        found.extend(checker(row.get(name)))
    return found


def invoices_policy_card(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'domain': DOMAIN_KEY,
        'title': DOMAIN_TITLE,
        'band': invoices_risk_band(row),
        'owner': invoices_owner_hint(row),
        'sla_hours': invoices_sla_hours(row),
        'exceptions': invoices_exception_needed(row),
        'freeze': invoices_freeze_window(row),
        'violations': policy.collect(row) + invoices_run_field_checks(row),
        'summary': invoices_summary_line(row),
    }

