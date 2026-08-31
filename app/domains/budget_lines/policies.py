"""Policy engine for Budget Lines.

Annual envelopes, owners, and consumed-to-date figures.
Operators use these guards before a write is allowed to settle.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

DOMAIN_KEY = 'budget_lines'
DOMAIN_TITLE = 'Budget Lines'
ACCENT = '#4ade80'
STATUSES = ['open', 'watch', 'frozen', 'closed']
SOFT_HOLD_STATUSES = ['frozen', 'closed']


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ''):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def budget_lines_policy_version() -> str:
    return 'budget_lines.policy.4'


def budget_lines_is_terminal(status: str) -> bool:
    return status == 'closed'


def budget_lines_requires_dual_control(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status in SOFT_HOLD_STATUSES:
        return True
    score = _as_int(row.get('health_score'))
    return score < 35


class BudgetLinesPolicy:
    """Named checks that finance, people, and platform leads can quote."""

    def __init__(self) -> None:
        self.domain = 'budget_lines'
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
            self.violations.append('Budget Lines: status is missing.')
            return
        if status not in STATUSES:
            self.violations.append('Budget Lines: status is outside the published ladder.')

    def check_identity(self, row: dict[str, Any]) -> None:
        record_id = str(row.get('id') or '')
        if record_id and ' ' in record_id:
            self.violations.append('Budget Lines: record id cannot contain spaces.')

    def check_freshness(self, row: dict[str, Any]) -> None:
        stamp = str(row.get('updated_at') or '')
        if not stamp:
            return
        try:
            parsed = datetime.fromisoformat(stamp.replace('Z', ''))
        except ValueError:
            self.violations.append('Budget Lines: updated_at is not parseable.')
            return
        age = (datetime.utcnow() - parsed).days
        if age > 800:
            self.violations.append('Budget Lines: record is older than the archive window.')

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
                self.violations.append('Budget Lines: ' + name + ' is out of bounds.')

    def check_text_hygiene(self, row: dict[str, Any]) -> None:
        for name, value in row.items():
            if not isinstance(value, str):
                continue
            if '\x00' in value:
                self.violations.append('Budget Lines: ' + name + ' contains a null byte.')
            if value != value.strip() and name not in ('comment',):
                self.violations.append('Budget Lines: ' + name + ' has surrounding whitespace.')

    def check_lifecycle(self, row: dict[str, Any]) -> None:
        status = str(row.get('status') or '')
        if status == 'closed' and _as_int(row.get('health_score')) > 90:
            self.violations.append('Budget Lines: terminal status with a high health score needs a note.')

    def allow_write(self, row: dict[str, Any]) -> bool:
        return not self.collect(row)


policy = BudgetLinesPolicy()


def budget_lines_gate_create(payload: dict[str, Any]) -> list[str]:
    return policy.collect(payload)


def budget_lines_gate_transition(current: str, nxt: str) -> list[str]:
    errors: list[str] = []
    if nxt not in STATUSES:
        errors.append('Budget Lines cannot move to an unknown status.')
    if current == 'closed' and nxt != current:
        if nxt not in STATUSES[:1]:
            errors.append('Budget Lines is sealed; only a reopen to the first status is modeled.')
    return errors


def budget_lines_risk_band(row: dict[str, Any]) -> str:
    score = _as_int(row.get('health_score'))
    if score >= 80:
        return 'calm'
    if score >= 55:
        return 'watch'
    if score >= 30:
        return 'elevated'
    return 'critical'


def budget_lines_owner_hint(row: dict[str, Any]) -> str:
    for candidate in ('owner', 'assignee', 'steward', 'manager', 'legal_owner', 'processor', 'host_name', 'sponsor'):
        value = str(row.get(candidate) or '').strip()
        if value:
            return value
    return 'unassigned-budget_lines'


def budget_lines_sla_hours(row: dict[str, Any]) -> int:
    band = budget_lines_risk_band(row)
    mapping = {'calm': 72, 'watch': 36, 'elevated': 12, 'critical': 4}
    return mapping[band]


def budget_lines_escalation_copy(row: dict[str, Any]) -> str:
    band = budget_lines_risk_band(row)
    owner = budget_lines_owner_hint(row)
    hours = budget_lines_sla_hours(row)
    return DOMAIN_TITLE + ' ' + band + ' item assigned to ' + owner + ' must move within ' + str(hours) + ' hours.'


PLAYBOOK_BUDGET_LINES = [
    {'step': 1, 'title': 'Triage', 'domain': 'budget_lines', 'hint': 'Triage for Budget Lines before the shift ends.'},
    {'step': 2, 'title': 'Confirm identifiers', 'domain': 'budget_lines', 'hint': 'Confirm identifiers for Budget Lines before the shift ends.'},
    {'step': 3, 'title': 'Check policy exceptions', 'domain': 'budget_lines', 'hint': 'Check policy exceptions for Budget Lines before the shift ends.'},
    {'step': 4, 'title': 'Notify the owner', 'domain': 'budget_lines', 'hint': 'Notify the owner for Budget Lines before the shift ends.'},
    {'step': 5, 'title': 'Capture evidence', 'domain': 'budget_lines', 'hint': 'Capture evidence for Budget Lines before the shift ends.'},
    {'step': 6, 'title': 'Propose a next status', 'domain': 'budget_lines', 'hint': 'Propose a next status for Budget Lines before the shift ends.'},
    {'step': 7, 'title': 'Record the decision', 'domain': 'budget_lines', 'hint': 'Record the decision for Budget Lines before the shift ends.'},
    {'step': 8, 'title': 'Close the loop with finance', 'domain': 'budget_lines', 'hint': 'Close the loop with finance for Budget Lines before the shift ends.'},
    {'step': 9, 'title': 'File the audit crumb', 'domain': 'budget_lines', 'hint': 'File the audit crumb for Budget Lines before the shift ends.'},
    {'step': 10, 'title': 'Schedule the next review', 'domain': 'budget_lines', 'hint': 'Schedule the next review for Budget Lines before the shift ends.'},
]


def budget_lines_playbook() -> list[dict[str, Any]]:
    return list(PLAYBOOK_BUDGET_LINES)


def budget_lines_exception_needed(row: dict[str, Any]) -> bool:
    return budget_lines_risk_band(row) in ('elevated', 'critical')


def budget_lines_freeze_window(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    return status in ['frozen', 'closed'] and date.today().weekday() >= 5


def budget_lines_summary_line(row: dict[str, Any]) -> str:
    ident = str(row.get('id') or 'new')
    status = str(row.get('status') or 'n/a')
    band = budget_lines_risk_band(row)
    return DOMAIN_TITLE + ' ' + ident + ' is ' + status + ' (' + band + ').'

def budget_lines_check_line_code(value: Any) -> list[str]:
    """Field policy for Line Code inside Budget Lines."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Line Code is required on Budget Lines.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Line Code is zero; confirm the Budget Lines case.')
        if number > 9_000_000_000:
            notes.append('Line Code exceeds the Budget Lines ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Line Code must be YYYY-MM-DD for Budget Lines.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Line Code is longer than the Budget Lines ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Line Code placeholder values are not allowed on Budget Lines.')
    return notes


def budget_lines_normalize_line_code(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def budget_lines_describe_line_code() -> str:
    required = 'required' if True else 'optional'
    return 'Line Code is a ' + required + ' str field on Budget Lines (budget_lines).'


def budget_lines_check_owner(value: Any) -> list[str]:
    """Field policy for Owner inside Budget Lines."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Owner is required on Budget Lines.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Owner is zero; confirm the Budget Lines case.')
        if number > 9_000_000_000:
            notes.append('Owner exceeds the Budget Lines ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Owner must be YYYY-MM-DD for Budget Lines.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Owner is longer than the Budget Lines ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Owner placeholder values are not allowed on Budget Lines.')
    return notes


def budget_lines_normalize_owner(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def budget_lines_describe_owner() -> str:
    required = 'required' if True else 'optional'
    return 'Owner is a ' + required + ' str field on Budget Lines (budget_lines).'


def budget_lines_check_annual_cents(value: Any) -> list[str]:
    """Field policy for Annual Cents inside Budget Lines."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Annual Cents is required on Budget Lines.')
        return notes
    if 'int' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Annual Cents is zero; confirm the Budget Lines case.')
        if number > 9_000_000_000:
            notes.append('Annual Cents exceeds the Budget Lines ceiling.')
        return notes
    if 'int' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Annual Cents must be YYYY-MM-DD for Budget Lines.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Annual Cents is longer than the Budget Lines ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Annual Cents placeholder values are not allowed on Budget Lines.')
    return notes


def budget_lines_normalize_annual_cents(value: Any) -> Any:
    if 'int' == 'int':
        return _as_int(value)
    if 'int' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def budget_lines_describe_annual_cents() -> str:
    required = 'required' if True else 'optional'
    return 'Annual Cents is a ' + required + ' int field on Budget Lines (budget_lines).'


def budget_lines_check_spent_cents(value: Any) -> list[str]:
    """Field policy for Spent Cents inside Budget Lines."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Spent Cents is required on Budget Lines.')
        return notes
    if 'int' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Spent Cents is zero; confirm the Budget Lines case.')
        if number > 9_000_000_000:
            notes.append('Spent Cents exceeds the Budget Lines ceiling.')
        return notes
    if 'int' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Spent Cents must be YYYY-MM-DD for Budget Lines.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Spent Cents is longer than the Budget Lines ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Spent Cents placeholder values are not allowed on Budget Lines.')
    return notes


def budget_lines_normalize_spent_cents(value: Any) -> Any:
    if 'int' == 'int':
        return _as_int(value)
    if 'int' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def budget_lines_describe_spent_cents() -> str:
    required = 'required' if True else 'optional'
    return 'Spent Cents is a ' + required + ' int field on Budget Lines (budget_lines).'


def budget_lines_check_status(value: Any) -> list[str]:
    """Field policy for Status inside Budget Lines."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Status is required on Budget Lines.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Status is zero; confirm the Budget Lines case.')
        if number > 9_000_000_000:
            notes.append('Status exceeds the Budget Lines ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Status must be YYYY-MM-DD for Budget Lines.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Status is longer than the Budget Lines ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Status placeholder values are not allowed on Budget Lines.')
    return notes


def budget_lines_normalize_status(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def budget_lines_describe_status() -> str:
    required = 'required' if True else 'optional'
    return 'Status is a ' + required + ' str field on Budget Lines (budget_lines).'


FIELD_CHECKS_BUDGET_LINES = {
    'line_code': budget_lines_check_line_code,
    'owner': budget_lines_check_owner,
    'annual_cents': budget_lines_check_annual_cents,
    'spent_cents': budget_lines_check_spent_cents,
    'status': budget_lines_check_status,
}


def budget_lines_run_field_checks(row: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for name, checker in FIELD_CHECKS_BUDGET_LINES.items():
        found.extend(checker(row.get(name)))
    return found


def budget_lines_policy_card(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'domain': DOMAIN_KEY,
        'title': DOMAIN_TITLE,
        'band': budget_lines_risk_band(row),
        'owner': budget_lines_owner_hint(row),
        'sla_hours': budget_lines_sla_hours(row),
        'exceptions': budget_lines_exception_needed(row),
        'freeze': budget_lines_freeze_window(row),
        'violations': policy.collect(row) + budget_lines_run_field_checks(row),
        'summary': budget_lines_summary_line(row),
    }

