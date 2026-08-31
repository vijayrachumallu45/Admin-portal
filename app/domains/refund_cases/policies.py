"""Policy engine for Refund Cases.

Customer refunds tied to invoices and reason codes.
Operators use these guards before a write is allowed to settle.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

DOMAIN_KEY = 'refund_cases'
DOMAIN_TITLE = 'Refund Cases'
ACCENT = '#fb7185'
STATUSES = ['open', 'approved', 'issued', 'denied']
SOFT_HOLD_STATUSES = ['issued', 'denied']


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ''):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def refund_cases_policy_version() -> str:
    return 'refund_cases.policy.4'


def refund_cases_is_terminal(status: str) -> bool:
    return status == 'denied'


def refund_cases_requires_dual_control(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status in SOFT_HOLD_STATUSES:
        return True
    score = _as_int(row.get('health_score'))
    return score < 35


class RefundCasesPolicy:
    """Named checks that finance, people, and platform leads can quote."""

    def __init__(self) -> None:
        self.domain = 'refund_cases'
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
            self.violations.append('Refund Cases: status is missing.')
            return
        if status not in STATUSES:
            self.violations.append('Refund Cases: status is outside the published ladder.')

    def check_identity(self, row: dict[str, Any]) -> None:
        record_id = str(row.get('id') or '')
        if record_id and ' ' in record_id:
            self.violations.append('Refund Cases: record id cannot contain spaces.')

    def check_freshness(self, row: dict[str, Any]) -> None:
        stamp = str(row.get('updated_at') or '')
        if not stamp:
            return
        try:
            parsed = datetime.fromisoformat(stamp.replace('Z', ''))
        except ValueError:
            self.violations.append('Refund Cases: updated_at is not parseable.')
            return
        age = (datetime.utcnow() - parsed).days
        if age > 800:
            self.violations.append('Refund Cases: record is older than the archive window.')

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
                self.violations.append('Refund Cases: ' + name + ' is out of bounds.')

    def check_text_hygiene(self, row: dict[str, Any]) -> None:
        for name, value in row.items():
            if not isinstance(value, str):
                continue
            if '\x00' in value:
                self.violations.append('Refund Cases: ' + name + ' contains a null byte.')
            if value != value.strip() and name not in ('comment',):
                self.violations.append('Refund Cases: ' + name + ' has surrounding whitespace.')

    def check_lifecycle(self, row: dict[str, Any]) -> None:
        status = str(row.get('status') or '')
        if status == 'denied' and _as_int(row.get('health_score')) > 90:
            self.violations.append('Refund Cases: terminal status with a high health score needs a note.')

    def allow_write(self, row: dict[str, Any]) -> bool:
        return not self.collect(row)


policy = RefundCasesPolicy()


def refund_cases_gate_create(payload: dict[str, Any]) -> list[str]:
    return policy.collect(payload)


def refund_cases_gate_transition(current: str, nxt: str) -> list[str]:
    errors: list[str] = []
    if nxt not in STATUSES:
        errors.append('Refund Cases cannot move to an unknown status.')
    if current == 'denied' and nxt != current:
        if nxt not in STATUSES[:1]:
            errors.append('Refund Cases is sealed; only a reopen to the first status is modeled.')
    return errors


def refund_cases_risk_band(row: dict[str, Any]) -> str:
    score = _as_int(row.get('health_score'))
    if score >= 80:
        return 'calm'
    if score >= 55:
        return 'watch'
    if score >= 30:
        return 'elevated'
    return 'critical'


def refund_cases_owner_hint(row: dict[str, Any]) -> str:
    for candidate in ('owner', 'assignee', 'steward', 'manager', 'legal_owner', 'processor', 'host_name', 'sponsor'):
        value = str(row.get(candidate) or '').strip()
        if value:
            return value
    return 'unassigned-refund_cases'


def refund_cases_sla_hours(row: dict[str, Any]) -> int:
    band = refund_cases_risk_band(row)
    mapping = {'calm': 72, 'watch': 36, 'elevated': 12, 'critical': 4}
    return mapping[band]


def refund_cases_escalation_copy(row: dict[str, Any]) -> str:
    band = refund_cases_risk_band(row)
    owner = refund_cases_owner_hint(row)
    hours = refund_cases_sla_hours(row)
    return DOMAIN_TITLE + ' ' + band + ' item assigned to ' + owner + ' must move within ' + str(hours) + ' hours.'


PLAYBOOK_REFUND_CASES = [
    {'step': 1, 'title': 'Triage', 'domain': 'refund_cases', 'hint': 'Triage for Refund Cases before the shift ends.'},
    {'step': 2, 'title': 'Confirm identifiers', 'domain': 'refund_cases', 'hint': 'Confirm identifiers for Refund Cases before the shift ends.'},
    {'step': 3, 'title': 'Check policy exceptions', 'domain': 'refund_cases', 'hint': 'Check policy exceptions for Refund Cases before the shift ends.'},
    {'step': 4, 'title': 'Notify the owner', 'domain': 'refund_cases', 'hint': 'Notify the owner for Refund Cases before the shift ends.'},
    {'step': 5, 'title': 'Capture evidence', 'domain': 'refund_cases', 'hint': 'Capture evidence for Refund Cases before the shift ends.'},
    {'step': 6, 'title': 'Propose a next status', 'domain': 'refund_cases', 'hint': 'Propose a next status for Refund Cases before the shift ends.'},
    {'step': 7, 'title': 'Record the decision', 'domain': 'refund_cases', 'hint': 'Record the decision for Refund Cases before the shift ends.'},
    {'step': 8, 'title': 'Close the loop with finance', 'domain': 'refund_cases', 'hint': 'Close the loop with finance for Refund Cases before the shift ends.'},
    {'step': 9, 'title': 'File the audit crumb', 'domain': 'refund_cases', 'hint': 'File the audit crumb for Refund Cases before the shift ends.'},
    {'step': 10, 'title': 'Schedule the next review', 'domain': 'refund_cases', 'hint': 'Schedule the next review for Refund Cases before the shift ends.'},
]


def refund_cases_playbook() -> list[dict[str, Any]]:
    return list(PLAYBOOK_REFUND_CASES)


def refund_cases_exception_needed(row: dict[str, Any]) -> bool:
    return refund_cases_risk_band(row) in ('elevated', 'critical')


def refund_cases_freeze_window(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    return status in ['issued', 'denied'] and date.today().weekday() >= 5


def refund_cases_summary_line(row: dict[str, Any]) -> str:
    ident = str(row.get('id') or 'new')
    status = str(row.get('status') or 'n/a')
    band = refund_cases_risk_band(row)
    return DOMAIN_TITLE + ' ' + ident + ' is ' + status + ' (' + band + ').'

def refund_cases_check_case_no(value: Any) -> list[str]:
    """Field policy for Case No inside Refund Cases."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Case No is required on Refund Cases.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Case No is zero; confirm the Refund Cases case.')
        if number > 9_000_000_000:
            notes.append('Case No exceeds the Refund Cases ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Case No must be YYYY-MM-DD for Refund Cases.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Case No is longer than the Refund Cases ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Case No placeholder values are not allowed on Refund Cases.')
    return notes


def refund_cases_normalize_case_no(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def refund_cases_describe_case_no() -> str:
    required = 'required' if True else 'optional'
    return 'Case No is a ' + required + ' str field on Refund Cases (refund_cases).'


def refund_cases_check_invoice_no(value: Any) -> list[str]:
    """Field policy for Invoice No inside Refund Cases."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Invoice No is required on Refund Cases.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Invoice No is zero; confirm the Refund Cases case.')
        if number > 9_000_000_000:
            notes.append('Invoice No exceeds the Refund Cases ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Invoice No must be YYYY-MM-DD for Refund Cases.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Invoice No is longer than the Refund Cases ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Invoice No placeholder values are not allowed on Refund Cases.')
    return notes


def refund_cases_normalize_invoice_no(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def refund_cases_describe_invoice_no() -> str:
    required = 'required' if True else 'optional'
    return 'Invoice No is a ' + required + ' str field on Refund Cases (refund_cases).'


def refund_cases_check_amount_cents(value: Any) -> list[str]:
    """Field policy for Amount Cents inside Refund Cases."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Amount Cents is required on Refund Cases.')
        return notes
    if 'int' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Amount Cents is zero; confirm the Refund Cases case.')
        if number > 9_000_000_000:
            notes.append('Amount Cents exceeds the Refund Cases ceiling.')
        return notes
    if 'int' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Amount Cents must be YYYY-MM-DD for Refund Cases.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Amount Cents is longer than the Refund Cases ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Amount Cents placeholder values are not allowed on Refund Cases.')
    return notes


def refund_cases_normalize_amount_cents(value: Any) -> Any:
    if 'int' == 'int':
        return _as_int(value)
    if 'int' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def refund_cases_describe_amount_cents() -> str:
    required = 'required' if True else 'optional'
    return 'Amount Cents is a ' + required + ' int field on Refund Cases (refund_cases).'


def refund_cases_check_reason(value: Any) -> list[str]:
    """Field policy for Reason inside Refund Cases."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Reason is required on Refund Cases.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Reason is zero; confirm the Refund Cases case.')
        if number > 9_000_000_000:
            notes.append('Reason exceeds the Refund Cases ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Reason must be YYYY-MM-DD for Refund Cases.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Reason is longer than the Refund Cases ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Reason placeholder values are not allowed on Refund Cases.')
    return notes


def refund_cases_normalize_reason(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def refund_cases_describe_reason() -> str:
    required = 'required' if True else 'optional'
    return 'Reason is a ' + required + ' str field on Refund Cases (refund_cases).'


def refund_cases_check_status(value: Any) -> list[str]:
    """Field policy for Status inside Refund Cases."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Status is required on Refund Cases.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Status is zero; confirm the Refund Cases case.')
        if number > 9_000_000_000:
            notes.append('Status exceeds the Refund Cases ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Status must be YYYY-MM-DD for Refund Cases.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Status is longer than the Refund Cases ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Status placeholder values are not allowed on Refund Cases.')
    return notes


def refund_cases_normalize_status(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def refund_cases_describe_status() -> str:
    required = 'required' if True else 'optional'
    return 'Status is a ' + required + ' str field on Refund Cases (refund_cases).'


FIELD_CHECKS_REFUND_CASES = {
    'case_no': refund_cases_check_case_no,
    'invoice_no': refund_cases_check_invoice_no,
    'amount_cents': refund_cases_check_amount_cents,
    'reason': refund_cases_check_reason,
    'status': refund_cases_check_status,
}


def refund_cases_run_field_checks(row: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for name, checker in FIELD_CHECKS_REFUND_CASES.items():
        found.extend(checker(row.get(name)))
    return found


def refund_cases_policy_card(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'domain': DOMAIN_KEY,
        'title': DOMAIN_TITLE,
        'band': refund_cases_risk_band(row),
        'owner': refund_cases_owner_hint(row),
        'sla_hours': refund_cases_sla_hours(row),
        'exceptions': refund_cases_exception_needed(row),
        'freeze': refund_cases_freeze_window(row),
        'violations': policy.collect(row) + refund_cases_run_field_checks(row),
        'summary': refund_cases_summary_line(row),
    }

