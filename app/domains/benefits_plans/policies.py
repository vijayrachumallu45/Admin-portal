"""Policy engine for Benefits Plans.

Coverage options, eligibility, and enrollment windows.
Operators use these guards before a write is allowed to settle.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

DOMAIN_KEY = 'benefits_plans'
DOMAIN_TITLE = 'Benefits Plans'
ACCENT = '#86efac'
STATUSES = ['draft', 'open', 'closed']
SOFT_HOLD_STATUSES = ['open', 'closed']


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ''):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def benefits_plans_policy_version() -> str:
    return 'benefits_plans.policy.4'


def benefits_plans_is_terminal(status: str) -> bool:
    return status == 'closed'


def benefits_plans_requires_dual_control(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status in SOFT_HOLD_STATUSES:
        return True
    score = _as_int(row.get('health_score'))
    return score < 35


class BenefitsPlansPolicy:
    """Named checks that finance, people, and platform leads can quote."""

    def __init__(self) -> None:
        self.domain = 'benefits_plans'
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
            self.violations.append('Benefits Plans: status is missing.')
            return
        if status not in STATUSES:
            self.violations.append('Benefits Plans: status is outside the published ladder.')

    def check_identity(self, row: dict[str, Any]) -> None:
        record_id = str(row.get('id') or '')
        if record_id and ' ' in record_id:
            self.violations.append('Benefits Plans: record id cannot contain spaces.')

    def check_freshness(self, row: dict[str, Any]) -> None:
        stamp = str(row.get('updated_at') or '')
        if not stamp:
            return
        try:
            parsed = datetime.fromisoformat(stamp.replace('Z', ''))
        except ValueError:
            self.violations.append('Benefits Plans: updated_at is not parseable.')
            return
        age = (datetime.utcnow() - parsed).days
        if age > 800:
            self.violations.append('Benefits Plans: record is older than the archive window.')

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
                self.violations.append('Benefits Plans: ' + name + ' is out of bounds.')

    def check_text_hygiene(self, row: dict[str, Any]) -> None:
        for name, value in row.items():
            if not isinstance(value, str):
                continue
            if '\x00' in value:
                self.violations.append('Benefits Plans: ' + name + ' contains a null byte.')
            if value != value.strip() and name not in ('comment',):
                self.violations.append('Benefits Plans: ' + name + ' has surrounding whitespace.')

    def check_lifecycle(self, row: dict[str, Any]) -> None:
        status = str(row.get('status') or '')
        if status == 'closed' and _as_int(row.get('health_score')) > 90:
            self.violations.append('Benefits Plans: terminal status with a high health score needs a note.')

    def allow_write(self, row: dict[str, Any]) -> bool:
        return not self.collect(row)


policy = BenefitsPlansPolicy()


def benefits_plans_gate_create(payload: dict[str, Any]) -> list[str]:
    return policy.collect(payload)


def benefits_plans_gate_transition(current: str, nxt: str) -> list[str]:
    errors: list[str] = []
    if nxt not in STATUSES:
        errors.append('Benefits Plans cannot move to an unknown status.')
    if current == 'closed' and nxt != current:
        if nxt not in STATUSES[:1]:
            errors.append('Benefits Plans is sealed; only a reopen to the first status is modeled.')
    return errors


def benefits_plans_risk_band(row: dict[str, Any]) -> str:
    score = _as_int(row.get('health_score'))
    if score >= 80:
        return 'calm'
    if score >= 55:
        return 'watch'
    if score >= 30:
        return 'elevated'
    return 'critical'


def benefits_plans_owner_hint(row: dict[str, Any]) -> str:
    for candidate in ('owner', 'assignee', 'steward', 'manager', 'legal_owner', 'processor', 'host_name', 'sponsor'):
        value = str(row.get(candidate) or '').strip()
        if value:
            return value
    return 'unassigned-benefits_plans'


def benefits_plans_sla_hours(row: dict[str, Any]) -> int:
    band = benefits_plans_risk_band(row)
    mapping = {'calm': 72, 'watch': 36, 'elevated': 12, 'critical': 4}
    return mapping[band]


def benefits_plans_escalation_copy(row: dict[str, Any]) -> str:
    band = benefits_plans_risk_band(row)
    owner = benefits_plans_owner_hint(row)
    hours = benefits_plans_sla_hours(row)
    return DOMAIN_TITLE + ' ' + band + ' item assigned to ' + owner + ' must move within ' + str(hours) + ' hours.'


PLAYBOOK_BENEFITS_PLANS = [
    {'step': 1, 'title': 'Triage', 'domain': 'benefits_plans', 'hint': 'Triage for Benefits Plans before the shift ends.'},
    {'step': 2, 'title': 'Confirm identifiers', 'domain': 'benefits_plans', 'hint': 'Confirm identifiers for Benefits Plans before the shift ends.'},
    {'step': 3, 'title': 'Check policy exceptions', 'domain': 'benefits_plans', 'hint': 'Check policy exceptions for Benefits Plans before the shift ends.'},
    {'step': 4, 'title': 'Notify the owner', 'domain': 'benefits_plans', 'hint': 'Notify the owner for Benefits Plans before the shift ends.'},
    {'step': 5, 'title': 'Capture evidence', 'domain': 'benefits_plans', 'hint': 'Capture evidence for Benefits Plans before the shift ends.'},
    {'step': 6, 'title': 'Propose a next status', 'domain': 'benefits_plans', 'hint': 'Propose a next status for Benefits Plans before the shift ends.'},
    {'step': 7, 'title': 'Record the decision', 'domain': 'benefits_plans', 'hint': 'Record the decision for Benefits Plans before the shift ends.'},
    {'step': 8, 'title': 'Close the loop with finance', 'domain': 'benefits_plans', 'hint': 'Close the loop with finance for Benefits Plans before the shift ends.'},
    {'step': 9, 'title': 'File the audit crumb', 'domain': 'benefits_plans', 'hint': 'File the audit crumb for Benefits Plans before the shift ends.'},
    {'step': 10, 'title': 'Schedule the next review', 'domain': 'benefits_plans', 'hint': 'Schedule the next review for Benefits Plans before the shift ends.'},
]


def benefits_plans_playbook() -> list[dict[str, Any]]:
    return list(PLAYBOOK_BENEFITS_PLANS)


def benefits_plans_exception_needed(row: dict[str, Any]) -> bool:
    return benefits_plans_risk_band(row) in ('elevated', 'critical')


def benefits_plans_freeze_window(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    return status in ['open', 'closed'] and date.today().weekday() >= 5


def benefits_plans_summary_line(row: dict[str, Any]) -> str:
    ident = str(row.get('id') or 'new')
    status = str(row.get('status') or 'n/a')
    band = benefits_plans_risk_band(row)
    return DOMAIN_TITLE + ' ' + ident + ' is ' + status + ' (' + band + ').'

def benefits_plans_check_plan_code(value: Any) -> list[str]:
    """Field policy for Plan Code inside Benefits Plans."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Plan Code is required on Benefits Plans.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Plan Code is zero; confirm the Benefits Plans case.')
        if number > 9_000_000_000:
            notes.append('Plan Code exceeds the Benefits Plans ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Plan Code must be YYYY-MM-DD for Benefits Plans.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Plan Code is longer than the Benefits Plans ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Plan Code placeholder values are not allowed on Benefits Plans.')
    return notes


def benefits_plans_normalize_plan_code(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def benefits_plans_describe_plan_code() -> str:
    required = 'required' if True else 'optional'
    return 'Plan Code is a ' + required + ' str field on Benefits Plans (benefits_plans).'


def benefits_plans_check_plan_name(value: Any) -> list[str]:
    """Field policy for Plan Name inside Benefits Plans."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Plan Name is required on Benefits Plans.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Plan Name is zero; confirm the Benefits Plans case.')
        if number > 9_000_000_000:
            notes.append('Plan Name exceeds the Benefits Plans ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Plan Name must be YYYY-MM-DD for Benefits Plans.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Plan Name is longer than the Benefits Plans ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Plan Name placeholder values are not allowed on Benefits Plans.')
    return notes


def benefits_plans_normalize_plan_name(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def benefits_plans_describe_plan_name() -> str:
    required = 'required' if True else 'optional'
    return 'Plan Name is a ' + required + ' str field on Benefits Plans (benefits_plans).'


def benefits_plans_check_eligibility(value: Any) -> list[str]:
    """Field policy for Eligibility inside Benefits Plans."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Eligibility is required on Benefits Plans.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Eligibility is zero; confirm the Benefits Plans case.')
        if number > 9_000_000_000:
            notes.append('Eligibility exceeds the Benefits Plans ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Eligibility must be YYYY-MM-DD for Benefits Plans.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Eligibility is longer than the Benefits Plans ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Eligibility placeholder values are not allowed on Benefits Plans.')
    return notes


def benefits_plans_normalize_eligibility(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def benefits_plans_describe_eligibility() -> str:
    required = 'required' if True else 'optional'
    return 'Eligibility is a ' + required + ' str field on Benefits Plans (benefits_plans).'


def benefits_plans_check_opens_on(value: Any) -> list[str]:
    """Field policy for Opens On inside Benefits Plans."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Opens On is required on Benefits Plans.')
        return notes
    if 'date' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Opens On is zero; confirm the Benefits Plans case.')
        if number > 9_000_000_000:
            notes.append('Opens On exceeds the Benefits Plans ceiling.')
        return notes
    if 'date' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Opens On must be YYYY-MM-DD for Benefits Plans.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Opens On is longer than the Benefits Plans ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Opens On placeholder values are not allowed on Benefits Plans.')
    return notes


def benefits_plans_normalize_opens_on(value: Any) -> Any:
    if 'date' == 'int':
        return _as_int(value)
    if 'date' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def benefits_plans_describe_opens_on() -> str:
    required = 'required' if True else 'optional'
    return 'Opens On is a ' + required + ' date field on Benefits Plans (benefits_plans).'


def benefits_plans_check_status(value: Any) -> list[str]:
    """Field policy for Status inside Benefits Plans."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Status is required on Benefits Plans.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Status is zero; confirm the Benefits Plans case.')
        if number > 9_000_000_000:
            notes.append('Status exceeds the Benefits Plans ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Status must be YYYY-MM-DD for Benefits Plans.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Status is longer than the Benefits Plans ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Status placeholder values are not allowed on Benefits Plans.')
    return notes


def benefits_plans_normalize_status(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def benefits_plans_describe_status() -> str:
    required = 'required' if True else 'optional'
    return 'Status is a ' + required + ' str field on Benefits Plans (benefits_plans).'


FIELD_CHECKS_BENEFITS_PLANS = {
    'plan_code': benefits_plans_check_plan_code,
    'plan_name': benefits_plans_check_plan_name,
    'eligibility': benefits_plans_check_eligibility,
    'opens_on': benefits_plans_check_opens_on,
    'status': benefits_plans_check_status,
}


def benefits_plans_run_field_checks(row: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for name, checker in FIELD_CHECKS_BENEFITS_PLANS.items():
        found.extend(checker(row.get(name)))
    return found


def benefits_plans_policy_card(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'domain': DOMAIN_KEY,
        'title': DOMAIN_TITLE,
        'band': benefits_plans_risk_band(row),
        'owner': benefits_plans_owner_hint(row),
        'sla_hours': benefits_plans_sla_hours(row),
        'exceptions': benefits_plans_exception_needed(row),
        'freeze': benefits_plans_freeze_window(row),
        'violations': policy.collect(row) + benefits_plans_run_field_checks(row),
        'summary': benefits_plans_summary_line(row),
    }

