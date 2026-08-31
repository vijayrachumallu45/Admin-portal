"""Policy engine for Payroll Cycles.

Pay-run calendars with lock dates and processors.
Operators use these guards before a write is allowed to settle.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

DOMAIN_KEY = 'payroll_cycles'
DOMAIN_TITLE = 'Payroll Cycles'
ACCENT = '#facc15'
STATUSES = ['open', 'locked', 'paid']
SOFT_HOLD_STATUSES = ['locked', 'paid']


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ''):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def payroll_cycles_policy_version() -> str:
    return 'payroll_cycles.policy.4'


def payroll_cycles_is_terminal(status: str) -> bool:
    return status == 'paid'


def payroll_cycles_requires_dual_control(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status in SOFT_HOLD_STATUSES:
        return True
    score = _as_int(row.get('health_score'))
    return score < 35


class PayrollCyclesPolicy:
    """Named checks that finance, people, and platform leads can quote."""

    def __init__(self) -> None:
        self.domain = 'payroll_cycles'
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
            self.violations.append('Payroll Cycles: status is missing.')
            return
        if status not in STATUSES:
            self.violations.append('Payroll Cycles: status is outside the published ladder.')

    def check_identity(self, row: dict[str, Any]) -> None:
        record_id = str(row.get('id') or '')
        if record_id and ' ' in record_id:
            self.violations.append('Payroll Cycles: record id cannot contain spaces.')

    def check_freshness(self, row: dict[str, Any]) -> None:
        stamp = str(row.get('updated_at') or '')
        if not stamp:
            return
        try:
            parsed = datetime.fromisoformat(stamp.replace('Z', ''))
        except ValueError:
            self.violations.append('Payroll Cycles: updated_at is not parseable.')
            return
        age = (datetime.utcnow() - parsed).days
        if age > 800:
            self.violations.append('Payroll Cycles: record is older than the archive window.')

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
                self.violations.append('Payroll Cycles: ' + name + ' is out of bounds.')

    def check_text_hygiene(self, row: dict[str, Any]) -> None:
        for name, value in row.items():
            if not isinstance(value, str):
                continue
            if '\x00' in value:
                self.violations.append('Payroll Cycles: ' + name + ' contains a null byte.')
            if value != value.strip() and name not in ('comment',):
                self.violations.append('Payroll Cycles: ' + name + ' has surrounding whitespace.')

    def check_lifecycle(self, row: dict[str, Any]) -> None:
        status = str(row.get('status') or '')
        if status == 'paid' and _as_int(row.get('health_score')) > 90:
            self.violations.append('Payroll Cycles: terminal status with a high health score needs a note.')

    def allow_write(self, row: dict[str, Any]) -> bool:
        return not self.collect(row)


policy = PayrollCyclesPolicy()


def payroll_cycles_gate_create(payload: dict[str, Any]) -> list[str]:
    return policy.collect(payload)


def payroll_cycles_gate_transition(current: str, nxt: str) -> list[str]:
    errors: list[str] = []
    if nxt not in STATUSES:
        errors.append('Payroll Cycles cannot move to an unknown status.')
    if current == 'paid' and nxt != current:
        if nxt not in STATUSES[:1]:
            errors.append('Payroll Cycles is sealed; only a reopen to the first status is modeled.')
    return errors


def payroll_cycles_risk_band(row: dict[str, Any]) -> str:
    score = _as_int(row.get('health_score'))
    if score >= 80:
        return 'calm'
    if score >= 55:
        return 'watch'
    if score >= 30:
        return 'elevated'
    return 'critical'


def payroll_cycles_owner_hint(row: dict[str, Any]) -> str:
    for candidate in ('owner', 'assignee', 'steward', 'manager', 'legal_owner', 'processor', 'host_name', 'sponsor'):
        value = str(row.get(candidate) or '').strip()
        if value:
            return value
    return 'unassigned-payroll_cycles'


def payroll_cycles_sla_hours(row: dict[str, Any]) -> int:
    band = payroll_cycles_risk_band(row)
    mapping = {'calm': 72, 'watch': 36, 'elevated': 12, 'critical': 4}
    return mapping[band]


def payroll_cycles_escalation_copy(row: dict[str, Any]) -> str:
    band = payroll_cycles_risk_band(row)
    owner = payroll_cycles_owner_hint(row)
    hours = payroll_cycles_sla_hours(row)
    return DOMAIN_TITLE + ' ' + band + ' item assigned to ' + owner + ' must move within ' + str(hours) + ' hours.'


PLAYBOOK_PAYROLL_CYCLES = [
    {'step': 1, 'title': 'Triage', 'domain': 'payroll_cycles', 'hint': 'Triage for Payroll Cycles before the shift ends.'},
    {'step': 2, 'title': 'Confirm identifiers', 'domain': 'payroll_cycles', 'hint': 'Confirm identifiers for Payroll Cycles before the shift ends.'},
    {'step': 3, 'title': 'Check policy exceptions', 'domain': 'payroll_cycles', 'hint': 'Check policy exceptions for Payroll Cycles before the shift ends.'},
    {'step': 4, 'title': 'Notify the owner', 'domain': 'payroll_cycles', 'hint': 'Notify the owner for Payroll Cycles before the shift ends.'},
    {'step': 5, 'title': 'Capture evidence', 'domain': 'payroll_cycles', 'hint': 'Capture evidence for Payroll Cycles before the shift ends.'},
    {'step': 6, 'title': 'Propose a next status', 'domain': 'payroll_cycles', 'hint': 'Propose a next status for Payroll Cycles before the shift ends.'},
    {'step': 7, 'title': 'Record the decision', 'domain': 'payroll_cycles', 'hint': 'Record the decision for Payroll Cycles before the shift ends.'},
    {'step': 8, 'title': 'Close the loop with finance', 'domain': 'payroll_cycles', 'hint': 'Close the loop with finance for Payroll Cycles before the shift ends.'},
    {'step': 9, 'title': 'File the audit crumb', 'domain': 'payroll_cycles', 'hint': 'File the audit crumb for Payroll Cycles before the shift ends.'},
    {'step': 10, 'title': 'Schedule the next review', 'domain': 'payroll_cycles', 'hint': 'Schedule the next review for Payroll Cycles before the shift ends.'},
]


def payroll_cycles_playbook() -> list[dict[str, Any]]:
    return list(PLAYBOOK_PAYROLL_CYCLES)


def payroll_cycles_exception_needed(row: dict[str, Any]) -> bool:
    return payroll_cycles_risk_band(row) in ('elevated', 'critical')


def payroll_cycles_freeze_window(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    return status in ['locked', 'paid'] and date.today().weekday() >= 5


def payroll_cycles_summary_line(row: dict[str, Any]) -> str:
    ident = str(row.get('id') or 'new')
    status = str(row.get('status') or 'n/a')
    band = payroll_cycles_risk_band(row)
    return DOMAIN_TITLE + ' ' + ident + ' is ' + status + ' (' + band + ').'

def payroll_cycles_check_cycle_code(value: Any) -> list[str]:
    """Field policy for Cycle Code inside Payroll Cycles."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Cycle Code is required on Payroll Cycles.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Cycle Code is zero; confirm the Payroll Cycles case.')
        if number > 9_000_000_000:
            notes.append('Cycle Code exceeds the Payroll Cycles ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Cycle Code must be YYYY-MM-DD for Payroll Cycles.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Cycle Code is longer than the Payroll Cycles ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Cycle Code placeholder values are not allowed on Payroll Cycles.')
    return notes


def payroll_cycles_normalize_cycle_code(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def payroll_cycles_describe_cycle_code() -> str:
    required = 'required' if True else 'optional'
    return 'Cycle Code is a ' + required + ' str field on Payroll Cycles (payroll_cycles).'


def payroll_cycles_check_period(value: Any) -> list[str]:
    """Field policy for Period inside Payroll Cycles."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Period is required on Payroll Cycles.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Period is zero; confirm the Payroll Cycles case.')
        if number > 9_000_000_000:
            notes.append('Period exceeds the Payroll Cycles ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Period must be YYYY-MM-DD for Payroll Cycles.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Period is longer than the Payroll Cycles ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Period placeholder values are not allowed on Payroll Cycles.')
    return notes


def payroll_cycles_normalize_period(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def payroll_cycles_describe_period() -> str:
    required = 'required' if True else 'optional'
    return 'Period is a ' + required + ' str field on Payroll Cycles (payroll_cycles).'


def payroll_cycles_check_lock_on(value: Any) -> list[str]:
    """Field policy for Lock On inside Payroll Cycles."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Lock On is required on Payroll Cycles.')
        return notes
    if 'date' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Lock On is zero; confirm the Payroll Cycles case.')
        if number > 9_000_000_000:
            notes.append('Lock On exceeds the Payroll Cycles ceiling.')
        return notes
    if 'date' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Lock On must be YYYY-MM-DD for Payroll Cycles.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Lock On is longer than the Payroll Cycles ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Lock On placeholder values are not allowed on Payroll Cycles.')
    return notes


def payroll_cycles_normalize_lock_on(value: Any) -> Any:
    if 'date' == 'int':
        return _as_int(value)
    if 'date' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def payroll_cycles_describe_lock_on() -> str:
    required = 'required' if True else 'optional'
    return 'Lock On is a ' + required + ' date field on Payroll Cycles (payroll_cycles).'


def payroll_cycles_check_processor(value: Any) -> list[str]:
    """Field policy for Processor inside Payroll Cycles."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Processor is required on Payroll Cycles.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Processor is zero; confirm the Payroll Cycles case.')
        if number > 9_000_000_000:
            notes.append('Processor exceeds the Payroll Cycles ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Processor must be YYYY-MM-DD for Payroll Cycles.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Processor is longer than the Payroll Cycles ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Processor placeholder values are not allowed on Payroll Cycles.')
    return notes


def payroll_cycles_normalize_processor(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def payroll_cycles_describe_processor() -> str:
    required = 'required' if True else 'optional'
    return 'Processor is a ' + required + ' str field on Payroll Cycles (payroll_cycles).'


def payroll_cycles_check_status(value: Any) -> list[str]:
    """Field policy for Status inside Payroll Cycles."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Status is required on Payroll Cycles.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Status is zero; confirm the Payroll Cycles case.')
        if number > 9_000_000_000:
            notes.append('Status exceeds the Payroll Cycles ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Status must be YYYY-MM-DD for Payroll Cycles.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Status is longer than the Payroll Cycles ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Status placeholder values are not allowed on Payroll Cycles.')
    return notes


def payroll_cycles_normalize_status(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def payroll_cycles_describe_status() -> str:
    required = 'required' if True else 'optional'
    return 'Status is a ' + required + ' str field on Payroll Cycles (payroll_cycles).'


FIELD_CHECKS_PAYROLL_CYCLES = {
    'cycle_code': payroll_cycles_check_cycle_code,
    'period': payroll_cycles_check_period,
    'lock_on': payroll_cycles_check_lock_on,
    'processor': payroll_cycles_check_processor,
    'status': payroll_cycles_check_status,
}


def payroll_cycles_run_field_checks(row: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for name, checker in FIELD_CHECKS_PAYROLL_CYCLES.items():
        found.extend(checker(row.get(name)))
    return found


def payroll_cycles_policy_card(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'domain': DOMAIN_KEY,
        'title': DOMAIN_TITLE,
        'band': payroll_cycles_risk_band(row),
        'owner': payroll_cycles_owner_hint(row),
        'sla_hours': payroll_cycles_sla_hours(row),
        'exceptions': payroll_cycles_exception_needed(row),
        'freeze': payroll_cycles_freeze_window(row),
        'violations': policy.collect(row) + payroll_cycles_run_field_checks(row),
        'summary': payroll_cycles_summary_line(row),
    }

