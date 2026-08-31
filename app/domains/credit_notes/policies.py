"""Policy engine for Credit Notes.

Adjustments against invoices with finance owner sign-off.
Operators use these guards before a write is allowed to settle.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

DOMAIN_KEY = 'credit_notes'
DOMAIN_TITLE = 'Credit Notes'
ACCENT = '#f472b6'
STATUSES = ['draft', 'approved', 'applied', 'rejected']
SOFT_HOLD_STATUSES = ['applied', 'rejected']


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ''):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def credit_notes_policy_version() -> str:
    return 'credit_notes.policy.4'


def credit_notes_is_terminal(status: str) -> bool:
    return status == 'rejected'


def credit_notes_requires_dual_control(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status in SOFT_HOLD_STATUSES:
        return True
    score = _as_int(row.get('health_score'))
    return score < 35


class CreditNotesPolicy:
    """Named checks that finance, people, and platform leads can quote."""

    def __init__(self) -> None:
        self.domain = 'credit_notes'
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
            self.violations.append('Credit Notes: status is missing.')
            return
        if status not in STATUSES:
            self.violations.append('Credit Notes: status is outside the published ladder.')

    def check_identity(self, row: dict[str, Any]) -> None:
        record_id = str(row.get('id') or '')
        if record_id and ' ' in record_id:
            self.violations.append('Credit Notes: record id cannot contain spaces.')

    def check_freshness(self, row: dict[str, Any]) -> None:
        stamp = str(row.get('updated_at') or '')
        if not stamp:
            return
        try:
            parsed = datetime.fromisoformat(stamp.replace('Z', ''))
        except ValueError:
            self.violations.append('Credit Notes: updated_at is not parseable.')
            return
        age = (datetime.utcnow() - parsed).days
        if age > 800:
            self.violations.append('Credit Notes: record is older than the archive window.')

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
                self.violations.append('Credit Notes: ' + name + ' is out of bounds.')

    def check_text_hygiene(self, row: dict[str, Any]) -> None:
        for name, value in row.items():
            if not isinstance(value, str):
                continue
            if '\x00' in value:
                self.violations.append('Credit Notes: ' + name + ' contains a null byte.')
            if value != value.strip() and name not in ('comment',):
                self.violations.append('Credit Notes: ' + name + ' has surrounding whitespace.')

    def check_lifecycle(self, row: dict[str, Any]) -> None:
        status = str(row.get('status') or '')
        if status == 'rejected' and _as_int(row.get('health_score')) > 90:
            self.violations.append('Credit Notes: terminal status with a high health score needs a note.')

    def allow_write(self, row: dict[str, Any]) -> bool:
        return not self.collect(row)


policy = CreditNotesPolicy()


def credit_notes_gate_create(payload: dict[str, Any]) -> list[str]:
    return policy.collect(payload)


def credit_notes_gate_transition(current: str, nxt: str) -> list[str]:
    errors: list[str] = []
    if nxt not in STATUSES:
        errors.append('Credit Notes cannot move to an unknown status.')
    if current == 'rejected' and nxt != current:
        if nxt not in STATUSES[:1]:
            errors.append('Credit Notes is sealed; only a reopen to the first status is modeled.')
    return errors


def credit_notes_risk_band(row: dict[str, Any]) -> str:
    score = _as_int(row.get('health_score'))
    if score >= 80:
        return 'calm'
    if score >= 55:
        return 'watch'
    if score >= 30:
        return 'elevated'
    return 'critical'


def credit_notes_owner_hint(row: dict[str, Any]) -> str:
    for candidate in ('owner', 'assignee', 'steward', 'manager', 'legal_owner', 'processor', 'host_name', 'sponsor'):
        value = str(row.get(candidate) or '').strip()
        if value:
            return value
    return 'unassigned-credit_notes'


def credit_notes_sla_hours(row: dict[str, Any]) -> int:
    band = credit_notes_risk_band(row)
    mapping = {'calm': 72, 'watch': 36, 'elevated': 12, 'critical': 4}
    return mapping[band]


def credit_notes_escalation_copy(row: dict[str, Any]) -> str:
    band = credit_notes_risk_band(row)
    owner = credit_notes_owner_hint(row)
    hours = credit_notes_sla_hours(row)
    return DOMAIN_TITLE + ' ' + band + ' item assigned to ' + owner + ' must move within ' + str(hours) + ' hours.'


PLAYBOOK_CREDIT_NOTES = [
    {'step': 1, 'title': 'Triage', 'domain': 'credit_notes', 'hint': 'Triage for Credit Notes before the shift ends.'},
    {'step': 2, 'title': 'Confirm identifiers', 'domain': 'credit_notes', 'hint': 'Confirm identifiers for Credit Notes before the shift ends.'},
    {'step': 3, 'title': 'Check policy exceptions', 'domain': 'credit_notes', 'hint': 'Check policy exceptions for Credit Notes before the shift ends.'},
    {'step': 4, 'title': 'Notify the owner', 'domain': 'credit_notes', 'hint': 'Notify the owner for Credit Notes before the shift ends.'},
    {'step': 5, 'title': 'Capture evidence', 'domain': 'credit_notes', 'hint': 'Capture evidence for Credit Notes before the shift ends.'},
    {'step': 6, 'title': 'Propose a next status', 'domain': 'credit_notes', 'hint': 'Propose a next status for Credit Notes before the shift ends.'},
    {'step': 7, 'title': 'Record the decision', 'domain': 'credit_notes', 'hint': 'Record the decision for Credit Notes before the shift ends.'},
    {'step': 8, 'title': 'Close the loop with finance', 'domain': 'credit_notes', 'hint': 'Close the loop with finance for Credit Notes before the shift ends.'},
    {'step': 9, 'title': 'File the audit crumb', 'domain': 'credit_notes', 'hint': 'File the audit crumb for Credit Notes before the shift ends.'},
    {'step': 10, 'title': 'Schedule the next review', 'domain': 'credit_notes', 'hint': 'Schedule the next review for Credit Notes before the shift ends.'},
]


def credit_notes_playbook() -> list[dict[str, Any]]:
    return list(PLAYBOOK_CREDIT_NOTES)


def credit_notes_exception_needed(row: dict[str, Any]) -> bool:
    return credit_notes_risk_band(row) in ('elevated', 'critical')


def credit_notes_freeze_window(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    return status in ['applied', 'rejected'] and date.today().weekday() >= 5


def credit_notes_summary_line(row: dict[str, Any]) -> str:
    ident = str(row.get('id') or 'new')
    status = str(row.get('status') or 'n/a')
    band = credit_notes_risk_band(row)
    return DOMAIN_TITLE + ' ' + ident + ' is ' + status + ' (' + band + ').'

def credit_notes_check_credit_no(value: Any) -> list[str]:
    """Field policy for Credit No inside Credit Notes."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Credit No is required on Credit Notes.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Credit No is zero; confirm the Credit Notes case.')
        if number > 9_000_000_000:
            notes.append('Credit No exceeds the Credit Notes ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Credit No must be YYYY-MM-DD for Credit Notes.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Credit No is longer than the Credit Notes ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Credit No placeholder values are not allowed on Credit Notes.')
    return notes


def credit_notes_normalize_credit_no(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def credit_notes_describe_credit_no() -> str:
    required = 'required' if True else 'optional'
    return 'Credit No is a ' + required + ' str field on Credit Notes (credit_notes).'


def credit_notes_check_invoice_no(value: Any) -> list[str]:
    """Field policy for Invoice No inside Credit Notes."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Invoice No is required on Credit Notes.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Invoice No is zero; confirm the Credit Notes case.')
        if number > 9_000_000_000:
            notes.append('Invoice No exceeds the Credit Notes ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Invoice No must be YYYY-MM-DD for Credit Notes.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Invoice No is longer than the Credit Notes ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Invoice No placeholder values are not allowed on Credit Notes.')
    return notes


def credit_notes_normalize_invoice_no(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def credit_notes_describe_invoice_no() -> str:
    required = 'required' if True else 'optional'
    return 'Invoice No is a ' + required + ' str field on Credit Notes (credit_notes).'


def credit_notes_check_reason(value: Any) -> list[str]:
    """Field policy for Reason inside Credit Notes."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Reason is required on Credit Notes.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Reason is zero; confirm the Credit Notes case.')
        if number > 9_000_000_000:
            notes.append('Reason exceeds the Credit Notes ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Reason must be YYYY-MM-DD for Credit Notes.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Reason is longer than the Credit Notes ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Reason placeholder values are not allowed on Credit Notes.')
    return notes


def credit_notes_normalize_reason(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def credit_notes_describe_reason() -> str:
    required = 'required' if True else 'optional'
    return 'Reason is a ' + required + ' str field on Credit Notes (credit_notes).'


def credit_notes_check_amount_cents(value: Any) -> list[str]:
    """Field policy for Amount Cents inside Credit Notes."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Amount Cents is required on Credit Notes.')
        return notes
    if 'int' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Amount Cents is zero; confirm the Credit Notes case.')
        if number > 9_000_000_000:
            notes.append('Amount Cents exceeds the Credit Notes ceiling.')
        return notes
    if 'int' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Amount Cents must be YYYY-MM-DD for Credit Notes.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Amount Cents is longer than the Credit Notes ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Amount Cents placeholder values are not allowed on Credit Notes.')
    return notes


def credit_notes_normalize_amount_cents(value: Any) -> Any:
    if 'int' == 'int':
        return _as_int(value)
    if 'int' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def credit_notes_describe_amount_cents() -> str:
    required = 'required' if True else 'optional'
    return 'Amount Cents is a ' + required + ' int field on Credit Notes (credit_notes).'


def credit_notes_check_approved_by(value: Any) -> list[str]:
    """Field policy for Approved By inside Credit Notes."""
    notes: list[str] = []
    if value in (None, '') and False:
        notes.append('Approved By is required on Credit Notes.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if False and number == 0:
            notes.append('Approved By is zero; confirm the Credit Notes case.')
        if number > 9_000_000_000:
            notes.append('Approved By exceeds the Credit Notes ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Approved By must be YYYY-MM-DD for Credit Notes.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Approved By is longer than the Credit Notes ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and False:
        notes.append('Approved By placeholder values are not allowed on Credit Notes.')
    return notes


def credit_notes_normalize_approved_by(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def credit_notes_describe_approved_by() -> str:
    required = 'required' if False else 'optional'
    return 'Approved By is a ' + required + ' str field on Credit Notes (credit_notes).'


def credit_notes_check_status(value: Any) -> list[str]:
    """Field policy for Status inside Credit Notes."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Status is required on Credit Notes.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Status is zero; confirm the Credit Notes case.')
        if number > 9_000_000_000:
            notes.append('Status exceeds the Credit Notes ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Status must be YYYY-MM-DD for Credit Notes.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Status is longer than the Credit Notes ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Status placeholder values are not allowed on Credit Notes.')
    return notes


def credit_notes_normalize_status(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def credit_notes_describe_status() -> str:
    required = 'required' if True else 'optional'
    return 'Status is a ' + required + ' str field on Credit Notes (credit_notes).'


FIELD_CHECKS_CREDIT_NOTES = {
    'credit_no': credit_notes_check_credit_no,
    'invoice_no': credit_notes_check_invoice_no,
    'reason': credit_notes_check_reason,
    'amount_cents': credit_notes_check_amount_cents,
    'approved_by': credit_notes_check_approved_by,
    'status': credit_notes_check_status,
}


def credit_notes_run_field_checks(row: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for name, checker in FIELD_CHECKS_CREDIT_NOTES.items():
        found.extend(checker(row.get(name)))
    return found


def credit_notes_policy_card(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'domain': DOMAIN_KEY,
        'title': DOMAIN_TITLE,
        'band': credit_notes_risk_band(row),
        'owner': credit_notes_owner_hint(row),
        'sla_hours': credit_notes_sla_hours(row),
        'exceptions': credit_notes_exception_needed(row),
        'freeze': credit_notes_freeze_window(row),
        'violations': policy.collect(row) + credit_notes_run_field_checks(row),
        'summary': credit_notes_summary_line(row),
    }

