"""Policy engine for Expense Reports.

Operator spend packs with policy checks and reimbursement stages.
Operators use these guards before a write is allowed to settle.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

DOMAIN_KEY = 'expense_reports'
DOMAIN_TITLE = 'Expense Reports'
ACCENT = '#f59e0b'
STATUSES = ['draft', 'submitted', 'approved', 'paid', 'rejected']
SOFT_HOLD_STATUSES = ['paid', 'rejected']


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ''):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def expense_reports_policy_version() -> str:
    return 'expense_reports.policy.4'


def expense_reports_is_terminal(status: str) -> bool:
    return status == 'rejected'


def expense_reports_requires_dual_control(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status in SOFT_HOLD_STATUSES:
        return True
    score = _as_int(row.get('health_score'))
    return score < 35


class ExpenseReportsPolicy:
    """Named checks that finance, people, and platform leads can quote."""

    def __init__(self) -> None:
        self.domain = 'expense_reports'
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
            self.violations.append('Expense Reports: status is missing.')
            return
        if status not in STATUSES:
            self.violations.append('Expense Reports: status is outside the published ladder.')

    def check_identity(self, row: dict[str, Any]) -> None:
        record_id = str(row.get('id') or '')
        if record_id and ' ' in record_id:
            self.violations.append('Expense Reports: record id cannot contain spaces.')

    def check_freshness(self, row: dict[str, Any]) -> None:
        stamp = str(row.get('updated_at') or '')
        if not stamp:
            return
        try:
            parsed = datetime.fromisoformat(stamp.replace('Z', ''))
        except ValueError:
            self.violations.append('Expense Reports: updated_at is not parseable.')
            return
        age = (datetime.utcnow() - parsed).days
        if age > 800:
            self.violations.append('Expense Reports: record is older than the archive window.')

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
                self.violations.append('Expense Reports: ' + name + ' is out of bounds.')

    def check_text_hygiene(self, row: dict[str, Any]) -> None:
        for name, value in row.items():
            if not isinstance(value, str):
                continue
            if '\x00' in value:
                self.violations.append('Expense Reports: ' + name + ' contains a null byte.')
            if value != value.strip() and name not in ('comment',):
                self.violations.append('Expense Reports: ' + name + ' has surrounding whitespace.')

    def check_lifecycle(self, row: dict[str, Any]) -> None:
        status = str(row.get('status') or '')
        if status == 'rejected' and _as_int(row.get('health_score')) > 90:
            self.violations.append('Expense Reports: terminal status with a high health score needs a note.')

    def allow_write(self, row: dict[str, Any]) -> bool:
        return not self.collect(row)


policy = ExpenseReportsPolicy()


def expense_reports_gate_create(payload: dict[str, Any]) -> list[str]:
    return policy.collect(payload)


def expense_reports_gate_transition(current: str, nxt: str) -> list[str]:
    errors: list[str] = []
    if nxt not in STATUSES:
        errors.append('Expense Reports cannot move to an unknown status.')
    if current == 'rejected' and nxt != current:
        if nxt not in STATUSES[:1]:
            errors.append('Expense Reports is sealed; only a reopen to the first status is modeled.')
    return errors


def expense_reports_risk_band(row: dict[str, Any]) -> str:
    score = _as_int(row.get('health_score'))
    if score >= 80:
        return 'calm'
    if score >= 55:
        return 'watch'
    if score >= 30:
        return 'elevated'
    return 'critical'


def expense_reports_owner_hint(row: dict[str, Any]) -> str:
    for candidate in ('owner', 'assignee', 'steward', 'manager', 'legal_owner', 'processor', 'host_name', 'sponsor'):
        value = str(row.get(candidate) or '').strip()
        if value:
            return value
    return 'unassigned-expense_reports'


def expense_reports_sla_hours(row: dict[str, Any]) -> int:
    band = expense_reports_risk_band(row)
    mapping = {'calm': 72, 'watch': 36, 'elevated': 12, 'critical': 4}
    return mapping[band]


def expense_reports_escalation_copy(row: dict[str, Any]) -> str:
    band = expense_reports_risk_band(row)
    owner = expense_reports_owner_hint(row)
    hours = expense_reports_sla_hours(row)
    return DOMAIN_TITLE + ' ' + band + ' item assigned to ' + owner + ' must move within ' + str(hours) + ' hours.'


PLAYBOOK_EXPENSE_REPORTS = [
    {'step': 1, 'title': 'Triage', 'domain': 'expense_reports', 'hint': 'Triage for Expense Reports before the shift ends.'},
    {'step': 2, 'title': 'Confirm identifiers', 'domain': 'expense_reports', 'hint': 'Confirm identifiers for Expense Reports before the shift ends.'},
    {'step': 3, 'title': 'Check policy exceptions', 'domain': 'expense_reports', 'hint': 'Check policy exceptions for Expense Reports before the shift ends.'},
    {'step': 4, 'title': 'Notify the owner', 'domain': 'expense_reports', 'hint': 'Notify the owner for Expense Reports before the shift ends.'},
    {'step': 5, 'title': 'Capture evidence', 'domain': 'expense_reports', 'hint': 'Capture evidence for Expense Reports before the shift ends.'},
    {'step': 6, 'title': 'Propose a next status', 'domain': 'expense_reports', 'hint': 'Propose a next status for Expense Reports before the shift ends.'},
    {'step': 7, 'title': 'Record the decision', 'domain': 'expense_reports', 'hint': 'Record the decision for Expense Reports before the shift ends.'},
    {'step': 8, 'title': 'Close the loop with finance', 'domain': 'expense_reports', 'hint': 'Close the loop with finance for Expense Reports before the shift ends.'},
    {'step': 9, 'title': 'File the audit crumb', 'domain': 'expense_reports', 'hint': 'File the audit crumb for Expense Reports before the shift ends.'},
    {'step': 10, 'title': 'Schedule the next review', 'domain': 'expense_reports', 'hint': 'Schedule the next review for Expense Reports before the shift ends.'},
]


def expense_reports_playbook() -> list[dict[str, Any]]:
    return list(PLAYBOOK_EXPENSE_REPORTS)


def expense_reports_exception_needed(row: dict[str, Any]) -> bool:
    return expense_reports_risk_band(row) in ('elevated', 'critical')


def expense_reports_freeze_window(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    return status in ['paid', 'rejected'] and date.today().weekday() >= 5


def expense_reports_summary_line(row: dict[str, Any]) -> str:
    ident = str(row.get('id') or 'new')
    status = str(row.get('status') or 'n/a')
    band = expense_reports_risk_band(row)
    return DOMAIN_TITLE + ' ' + ident + ' is ' + status + ' (' + band + ').'

def expense_reports_check_report_no(value: Any) -> list[str]:
    """Field policy for Report No inside Expense Reports."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Report No is required on Expense Reports.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Report No is zero; confirm the Expense Reports case.')
        if number > 9_000_000_000:
            notes.append('Report No exceeds the Expense Reports ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Report No must be YYYY-MM-DD for Expense Reports.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Report No is longer than the Expense Reports ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Report No placeholder values are not allowed on Expense Reports.')
    return notes


def expense_reports_normalize_report_no(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def expense_reports_describe_report_no() -> str:
    required = 'required' if True else 'optional'
    return 'Report No is a ' + required + ' str field on Expense Reports (expense_reports).'


def expense_reports_check_employee_no(value: Any) -> list[str]:
    """Field policy for Employee No inside Expense Reports."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Employee No is required on Expense Reports.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Employee No is zero; confirm the Expense Reports case.')
        if number > 9_000_000_000:
            notes.append('Employee No exceeds the Expense Reports ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Employee No must be YYYY-MM-DD for Expense Reports.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Employee No is longer than the Expense Reports ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Employee No placeholder values are not allowed on Expense Reports.')
    return notes


def expense_reports_normalize_employee_no(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def expense_reports_describe_employee_no() -> str:
    required = 'required' if True else 'optional'
    return 'Employee No is a ' + required + ' str field on Expense Reports (expense_reports).'


def expense_reports_check_amount_cents(value: Any) -> list[str]:
    """Field policy for Amount Cents inside Expense Reports."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Amount Cents is required on Expense Reports.')
        return notes
    if 'int' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Amount Cents is zero; confirm the Expense Reports case.')
        if number > 9_000_000_000:
            notes.append('Amount Cents exceeds the Expense Reports ceiling.')
        return notes
    if 'int' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Amount Cents must be YYYY-MM-DD for Expense Reports.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Amount Cents is longer than the Expense Reports ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Amount Cents placeholder values are not allowed on Expense Reports.')
    return notes


def expense_reports_normalize_amount_cents(value: Any) -> Any:
    if 'int' == 'int':
        return _as_int(value)
    if 'int' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def expense_reports_describe_amount_cents() -> str:
    required = 'required' if True else 'optional'
    return 'Amount Cents is a ' + required + ' int field on Expense Reports (expense_reports).'


def expense_reports_check_cost_center(value: Any) -> list[str]:
    """Field policy for Cost Center inside Expense Reports."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Cost Center is required on Expense Reports.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Cost Center is zero; confirm the Expense Reports case.')
        if number > 9_000_000_000:
            notes.append('Cost Center exceeds the Expense Reports ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Cost Center must be YYYY-MM-DD for Expense Reports.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Cost Center is longer than the Expense Reports ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Cost Center placeholder values are not allowed on Expense Reports.')
    return notes


def expense_reports_normalize_cost_center(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def expense_reports_describe_cost_center() -> str:
    required = 'required' if True else 'optional'
    return 'Cost Center is a ' + required + ' str field on Expense Reports (expense_reports).'


def expense_reports_check_submitted_on(value: Any) -> list[str]:
    """Field policy for Submitted On inside Expense Reports."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Submitted On is required on Expense Reports.')
        return notes
    if 'date' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Submitted On is zero; confirm the Expense Reports case.')
        if number > 9_000_000_000:
            notes.append('Submitted On exceeds the Expense Reports ceiling.')
        return notes
    if 'date' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Submitted On must be YYYY-MM-DD for Expense Reports.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Submitted On is longer than the Expense Reports ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Submitted On placeholder values are not allowed on Expense Reports.')
    return notes


def expense_reports_normalize_submitted_on(value: Any) -> Any:
    if 'date' == 'int':
        return _as_int(value)
    if 'date' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def expense_reports_describe_submitted_on() -> str:
    required = 'required' if True else 'optional'
    return 'Submitted On is a ' + required + ' date field on Expense Reports (expense_reports).'


def expense_reports_check_status(value: Any) -> list[str]:
    """Field policy for Status inside Expense Reports."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Status is required on Expense Reports.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Status is zero; confirm the Expense Reports case.')
        if number > 9_000_000_000:
            notes.append('Status exceeds the Expense Reports ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Status must be YYYY-MM-DD for Expense Reports.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Status is longer than the Expense Reports ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Status placeholder values are not allowed on Expense Reports.')
    return notes


def expense_reports_normalize_status(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def expense_reports_describe_status() -> str:
    required = 'required' if True else 'optional'
    return 'Status is a ' + required + ' str field on Expense Reports (expense_reports).'


FIELD_CHECKS_EXPENSE_REPORTS = {
    'report_no': expense_reports_check_report_no,
    'employee_no': expense_reports_check_employee_no,
    'amount_cents': expense_reports_check_amount_cents,
    'cost_center': expense_reports_check_cost_center,
    'submitted_on': expense_reports_check_submitted_on,
    'status': expense_reports_check_status,
}


def expense_reports_run_field_checks(row: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for name, checker in FIELD_CHECKS_EXPENSE_REPORTS.items():
        found.extend(checker(row.get(name)))
    return found


def expense_reports_policy_card(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'domain': DOMAIN_KEY,
        'title': DOMAIN_TITLE,
        'band': expense_reports_risk_band(row),
        'owner': expense_reports_owner_hint(row),
        'sla_hours': expense_reports_sla_hours(row),
        'exceptions': expense_reports_exception_needed(row),
        'freeze': expense_reports_freeze_window(row),
        'violations': policy.collect(row) + expense_reports_run_field_checks(row),
        'summary': expense_reports_summary_line(row),
    }

