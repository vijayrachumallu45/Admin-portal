"""Policy engine for Outbound Payments.

Vendor disbursements with approval trail and settlement dates.
Operators use these guards before a write is allowed to settle.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

DOMAIN_KEY = 'payments_out'
DOMAIN_TITLE = 'Outbound Payments'
ACCENT = '#34d399'
STATUSES = ['queued', 'approved', 'sent', 'failed', 'void']
SOFT_HOLD_STATUSES = ['failed', 'void']


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ''):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def payments_out_policy_version() -> str:
    return 'payments_out.policy.4'


def payments_out_is_terminal(status: str) -> bool:
    return status == 'void'


def payments_out_requires_dual_control(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status in SOFT_HOLD_STATUSES:
        return True
    score = _as_int(row.get('health_score'))
    return score < 35


class PaymentsOutPolicy:
    """Named checks that finance, people, and platform leads can quote."""

    def __init__(self) -> None:
        self.domain = 'payments_out'
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
            self.violations.append('Outbound Payments: status is missing.')
            return
        if status not in STATUSES:
            self.violations.append('Outbound Payments: status is outside the published ladder.')

    def check_identity(self, row: dict[str, Any]) -> None:
        record_id = str(row.get('id') or '')
        if record_id and ' ' in record_id:
            self.violations.append('Outbound Payments: record id cannot contain spaces.')

    def check_freshness(self, row: dict[str, Any]) -> None:
        stamp = str(row.get('updated_at') or '')
        if not stamp:
            return
        try:
            parsed = datetime.fromisoformat(stamp.replace('Z', ''))
        except ValueError:
            self.violations.append('Outbound Payments: updated_at is not parseable.')
            return
        age = (datetime.utcnow() - parsed).days
        if age > 800:
            self.violations.append('Outbound Payments: record is older than the archive window.')

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
                self.violations.append('Outbound Payments: ' + name + ' is out of bounds.')

    def check_text_hygiene(self, row: dict[str, Any]) -> None:
        for name, value in row.items():
            if not isinstance(value, str):
                continue
            if '\x00' in value:
                self.violations.append('Outbound Payments: ' + name + ' contains a null byte.')
            if value != value.strip() and name not in ('comment',):
                self.violations.append('Outbound Payments: ' + name + ' has surrounding whitespace.')

    def check_lifecycle(self, row: dict[str, Any]) -> None:
        status = str(row.get('status') or '')
        if status == 'void' and _as_int(row.get('health_score')) > 90:
            self.violations.append('Outbound Payments: terminal status with a high health score needs a note.')

    def allow_write(self, row: dict[str, Any]) -> bool:
        return not self.collect(row)


policy = PaymentsOutPolicy()


def payments_out_gate_create(payload: dict[str, Any]) -> list[str]:
    return policy.collect(payload)


def payments_out_gate_transition(current: str, nxt: str) -> list[str]:
    errors: list[str] = []
    if nxt not in STATUSES:
        errors.append('Outbound Payments cannot move to an unknown status.')
    if current == 'void' and nxt != current:
        if nxt not in STATUSES[:1]:
            errors.append('Outbound Payments is sealed; only a reopen to the first status is modeled.')
    return errors


def payments_out_risk_band(row: dict[str, Any]) -> str:
    score = _as_int(row.get('health_score'))
    if score >= 80:
        return 'calm'
    if score >= 55:
        return 'watch'
    if score >= 30:
        return 'elevated'
    return 'critical'


def payments_out_owner_hint(row: dict[str, Any]) -> str:
    for candidate in ('owner', 'assignee', 'steward', 'manager', 'legal_owner', 'processor', 'host_name', 'sponsor'):
        value = str(row.get(candidate) or '').strip()
        if value:
            return value
    return 'unassigned-payments_out'


def payments_out_sla_hours(row: dict[str, Any]) -> int:
    band = payments_out_risk_band(row)
    mapping = {'calm': 72, 'watch': 36, 'elevated': 12, 'critical': 4}
    return mapping[band]


def payments_out_escalation_copy(row: dict[str, Any]) -> str:
    band = payments_out_risk_band(row)
    owner = payments_out_owner_hint(row)
    hours = payments_out_sla_hours(row)
    return DOMAIN_TITLE + ' ' + band + ' item assigned to ' + owner + ' must move within ' + str(hours) + ' hours.'


PLAYBOOK_PAYMENTS_OUT = [
    {'step': 1, 'title': 'Triage', 'domain': 'payments_out', 'hint': 'Triage for Outbound Payments before the shift ends.'},
    {'step': 2, 'title': 'Confirm identifiers', 'domain': 'payments_out', 'hint': 'Confirm identifiers for Outbound Payments before the shift ends.'},
    {'step': 3, 'title': 'Check policy exceptions', 'domain': 'payments_out', 'hint': 'Check policy exceptions for Outbound Payments before the shift ends.'},
    {'step': 4, 'title': 'Notify the owner', 'domain': 'payments_out', 'hint': 'Notify the owner for Outbound Payments before the shift ends.'},
    {'step': 5, 'title': 'Capture evidence', 'domain': 'payments_out', 'hint': 'Capture evidence for Outbound Payments before the shift ends.'},
    {'step': 6, 'title': 'Propose a next status', 'domain': 'payments_out', 'hint': 'Propose a next status for Outbound Payments before the shift ends.'},
    {'step': 7, 'title': 'Record the decision', 'domain': 'payments_out', 'hint': 'Record the decision for Outbound Payments before the shift ends.'},
    {'step': 8, 'title': 'Close the loop with finance', 'domain': 'payments_out', 'hint': 'Close the loop with finance for Outbound Payments before the shift ends.'},
    {'step': 9, 'title': 'File the audit crumb', 'domain': 'payments_out', 'hint': 'File the audit crumb for Outbound Payments before the shift ends.'},
    {'step': 10, 'title': 'Schedule the next review', 'domain': 'payments_out', 'hint': 'Schedule the next review for Outbound Payments before the shift ends.'},
]


def payments_out_playbook() -> list[dict[str, Any]]:
    return list(PLAYBOOK_PAYMENTS_OUT)


def payments_out_exception_needed(row: dict[str, Any]) -> bool:
    return payments_out_risk_band(row) in ('elevated', 'critical')


def payments_out_freeze_window(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    return status in ['failed', 'void'] and date.today().weekday() >= 5


def payments_out_summary_line(row: dict[str, Any]) -> str:
    ident = str(row.get('id') or 'new')
    status = str(row.get('status') or 'n/a')
    band = payments_out_risk_band(row)
    return DOMAIN_TITLE + ' ' + ident + ' is ' + status + ' (' + band + ').'

def payments_out_check_payment_no(value: Any) -> list[str]:
    """Field policy for Payment No inside Outbound Payments."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Payment No is required on Outbound Payments.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Payment No is zero; confirm the Outbound Payments case.')
        if number > 9_000_000_000:
            notes.append('Payment No exceeds the Outbound Payments ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Payment No must be YYYY-MM-DD for Outbound Payments.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Payment No is longer than the Outbound Payments ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Payment No placeholder values are not allowed on Outbound Payments.')
    return notes


def payments_out_normalize_payment_no(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def payments_out_describe_payment_no() -> str:
    required = 'required' if True else 'optional'
    return 'Payment No is a ' + required + ' str field on Outbound Payments (payments_out).'


def payments_out_check_payee(value: Any) -> list[str]:
    """Field policy for Payee inside Outbound Payments."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Payee is required on Outbound Payments.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Payee is zero; confirm the Outbound Payments case.')
        if number > 9_000_000_000:
            notes.append('Payee exceeds the Outbound Payments ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Payee must be YYYY-MM-DD for Outbound Payments.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Payee is longer than the Outbound Payments ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Payee placeholder values are not allowed on Outbound Payments.')
    return notes


def payments_out_normalize_payee(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def payments_out_describe_payee() -> str:
    required = 'required' if True else 'optional'
    return 'Payee is a ' + required + ' str field on Outbound Payments (payments_out).'


def payments_out_check_amount_cents(value: Any) -> list[str]:
    """Field policy for Amount Cents inside Outbound Payments."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Amount Cents is required on Outbound Payments.')
        return notes
    if 'int' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Amount Cents is zero; confirm the Outbound Payments case.')
        if number > 9_000_000_000:
            notes.append('Amount Cents exceeds the Outbound Payments ceiling.')
        return notes
    if 'int' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Amount Cents must be YYYY-MM-DD for Outbound Payments.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Amount Cents is longer than the Outbound Payments ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Amount Cents placeholder values are not allowed on Outbound Payments.')
    return notes


def payments_out_normalize_amount_cents(value: Any) -> Any:
    if 'int' == 'int':
        return _as_int(value)
    if 'int' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def payments_out_describe_amount_cents() -> str:
    required = 'required' if True else 'optional'
    return 'Amount Cents is a ' + required + ' int field on Outbound Payments (payments_out).'


def payments_out_check_method(value: Any) -> list[str]:
    """Field policy for Method inside Outbound Payments."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Method is required on Outbound Payments.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Method is zero; confirm the Outbound Payments case.')
        if number > 9_000_000_000:
            notes.append('Method exceeds the Outbound Payments ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Method must be YYYY-MM-DD for Outbound Payments.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Method is longer than the Outbound Payments ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Method placeholder values are not allowed on Outbound Payments.')
    return notes


def payments_out_normalize_method(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def payments_out_describe_method() -> str:
    required = 'required' if True else 'optional'
    return 'Method is a ' + required + ' str field on Outbound Payments (payments_out).'


def payments_out_check_paid_on(value: Any) -> list[str]:
    """Field policy for Paid On inside Outbound Payments."""
    notes: list[str] = []
    if value in (None, '') and False:
        notes.append('Paid On is required on Outbound Payments.')
        return notes
    if 'date' == 'int':
        number = _as_int(value, default=0)
        if False and number == 0:
            notes.append('Paid On is zero; confirm the Outbound Payments case.')
        if number > 9_000_000_000:
            notes.append('Paid On exceeds the Outbound Payments ceiling.')
        return notes
    if 'date' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Paid On must be YYYY-MM-DD for Outbound Payments.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Paid On is longer than the Outbound Payments ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and False:
        notes.append('Paid On placeholder values are not allowed on Outbound Payments.')
    return notes


def payments_out_normalize_paid_on(value: Any) -> Any:
    if 'date' == 'int':
        return _as_int(value)
    if 'date' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def payments_out_describe_paid_on() -> str:
    required = 'required' if False else 'optional'
    return 'Paid On is a ' + required + ' date field on Outbound Payments (payments_out).'


def payments_out_check_status(value: Any) -> list[str]:
    """Field policy for Status inside Outbound Payments."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Status is required on Outbound Payments.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Status is zero; confirm the Outbound Payments case.')
        if number > 9_000_000_000:
            notes.append('Status exceeds the Outbound Payments ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Status must be YYYY-MM-DD for Outbound Payments.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Status is longer than the Outbound Payments ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Status placeholder values are not allowed on Outbound Payments.')
    return notes


def payments_out_normalize_status(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def payments_out_describe_status() -> str:
    required = 'required' if True else 'optional'
    return 'Status is a ' + required + ' str field on Outbound Payments (payments_out).'


FIELD_CHECKS_PAYMENTS_OUT = {
    'payment_no': payments_out_check_payment_no,
    'payee': payments_out_check_payee,
    'amount_cents': payments_out_check_amount_cents,
    'method': payments_out_check_method,
    'paid_on': payments_out_check_paid_on,
    'status': payments_out_check_status,
}


def payments_out_run_field_checks(row: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for name, checker in FIELD_CHECKS_PAYMENTS_OUT.items():
        found.extend(checker(row.get(name)))
    return found


def payments_out_policy_card(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'domain': DOMAIN_KEY,
        'title': DOMAIN_TITLE,
        'band': payments_out_risk_band(row),
        'owner': payments_out_owner_hint(row),
        'sla_hours': payments_out_sla_hours(row),
        'exceptions': payments_out_exception_needed(row),
        'freeze': payments_out_freeze_window(row),
        'violations': policy.collect(row) + payments_out_run_field_checks(row),
        'summary': payments_out_summary_line(row),
    }

