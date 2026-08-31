"""Policy engine for Cost Centers.

Finance nodes used to roll operational spend.
Operators use these guards before a write is allowed to settle.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

DOMAIN_KEY = 'cost_centers'
DOMAIN_TITLE = 'Cost Centers'
ACCENT = '#fbbf24'
STATUSES = ['active', 'merging', 'retired']
SOFT_HOLD_STATUSES = ['merging', 'retired']


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ''):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def cost_centers_policy_version() -> str:
    return 'cost_centers.policy.4'


def cost_centers_is_terminal(status: str) -> bool:
    return status == 'retired'


def cost_centers_requires_dual_control(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status in SOFT_HOLD_STATUSES:
        return True
    score = _as_int(row.get('health_score'))
    return score < 35


class CostCentersPolicy:
    """Named checks that finance, people, and platform leads can quote."""

    def __init__(self) -> None:
        self.domain = 'cost_centers'
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
            self.violations.append('Cost Centers: status is missing.')
            return
        if status not in STATUSES:
            self.violations.append('Cost Centers: status is outside the published ladder.')

    def check_identity(self, row: dict[str, Any]) -> None:
        record_id = str(row.get('id') or '')
        if record_id and ' ' in record_id:
            self.violations.append('Cost Centers: record id cannot contain spaces.')

    def check_freshness(self, row: dict[str, Any]) -> None:
        stamp = str(row.get('updated_at') or '')
        if not stamp:
            return
        try:
            parsed = datetime.fromisoformat(stamp.replace('Z', ''))
        except ValueError:
            self.violations.append('Cost Centers: updated_at is not parseable.')
            return
        age = (datetime.utcnow() - parsed).days
        if age > 800:
            self.violations.append('Cost Centers: record is older than the archive window.')

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
                self.violations.append('Cost Centers: ' + name + ' is out of bounds.')

    def check_text_hygiene(self, row: dict[str, Any]) -> None:
        for name, value in row.items():
            if not isinstance(value, str):
                continue
            if '\x00' in value:
                self.violations.append('Cost Centers: ' + name + ' contains a null byte.')
            if value != value.strip() and name not in ('comment',):
                self.violations.append('Cost Centers: ' + name + ' has surrounding whitespace.')

    def check_lifecycle(self, row: dict[str, Any]) -> None:
        status = str(row.get('status') or '')
        if status == 'retired' and _as_int(row.get('health_score')) > 90:
            self.violations.append('Cost Centers: terminal status with a high health score needs a note.')

    def allow_write(self, row: dict[str, Any]) -> bool:
        return not self.collect(row)


policy = CostCentersPolicy()


def cost_centers_gate_create(payload: dict[str, Any]) -> list[str]:
    return policy.collect(payload)


def cost_centers_gate_transition(current: str, nxt: str) -> list[str]:
    errors: list[str] = []
    if nxt not in STATUSES:
        errors.append('Cost Centers cannot move to an unknown status.')
    if current == 'retired' and nxt != current:
        if nxt not in STATUSES[:1]:
            errors.append('Cost Centers is sealed; only a reopen to the first status is modeled.')
    return errors


def cost_centers_risk_band(row: dict[str, Any]) -> str:
    score = _as_int(row.get('health_score'))
    if score >= 80:
        return 'calm'
    if score >= 55:
        return 'watch'
    if score >= 30:
        return 'elevated'
    return 'critical'


def cost_centers_owner_hint(row: dict[str, Any]) -> str:
    for candidate in ('owner', 'assignee', 'steward', 'manager', 'legal_owner', 'processor', 'host_name', 'sponsor'):
        value = str(row.get(candidate) or '').strip()
        if value:
            return value
    return 'unassigned-cost_centers'


def cost_centers_sla_hours(row: dict[str, Any]) -> int:
    band = cost_centers_risk_band(row)
    mapping = {'calm': 72, 'watch': 36, 'elevated': 12, 'critical': 4}
    return mapping[band]


def cost_centers_escalation_copy(row: dict[str, Any]) -> str:
    band = cost_centers_risk_band(row)
    owner = cost_centers_owner_hint(row)
    hours = cost_centers_sla_hours(row)
    return DOMAIN_TITLE + ' ' + band + ' item assigned to ' + owner + ' must move within ' + str(hours) + ' hours.'


PLAYBOOK_COST_CENTERS = [
    {'step': 1, 'title': 'Triage', 'domain': 'cost_centers', 'hint': 'Triage for Cost Centers before the shift ends.'},
    {'step': 2, 'title': 'Confirm identifiers', 'domain': 'cost_centers', 'hint': 'Confirm identifiers for Cost Centers before the shift ends.'},
    {'step': 3, 'title': 'Check policy exceptions', 'domain': 'cost_centers', 'hint': 'Check policy exceptions for Cost Centers before the shift ends.'},
    {'step': 4, 'title': 'Notify the owner', 'domain': 'cost_centers', 'hint': 'Notify the owner for Cost Centers before the shift ends.'},
    {'step': 5, 'title': 'Capture evidence', 'domain': 'cost_centers', 'hint': 'Capture evidence for Cost Centers before the shift ends.'},
    {'step': 6, 'title': 'Propose a next status', 'domain': 'cost_centers', 'hint': 'Propose a next status for Cost Centers before the shift ends.'},
    {'step': 7, 'title': 'Record the decision', 'domain': 'cost_centers', 'hint': 'Record the decision for Cost Centers before the shift ends.'},
    {'step': 8, 'title': 'Close the loop with finance', 'domain': 'cost_centers', 'hint': 'Close the loop with finance for Cost Centers before the shift ends.'},
    {'step': 9, 'title': 'File the audit crumb', 'domain': 'cost_centers', 'hint': 'File the audit crumb for Cost Centers before the shift ends.'},
    {'step': 10, 'title': 'Schedule the next review', 'domain': 'cost_centers', 'hint': 'Schedule the next review for Cost Centers before the shift ends.'},
]


def cost_centers_playbook() -> list[dict[str, Any]]:
    return list(PLAYBOOK_COST_CENTERS)


def cost_centers_exception_needed(row: dict[str, Any]) -> bool:
    return cost_centers_risk_band(row) in ('elevated', 'critical')


def cost_centers_freeze_window(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    return status in ['merging', 'retired'] and date.today().weekday() >= 5


def cost_centers_summary_line(row: dict[str, Any]) -> str:
    ident = str(row.get('id') or 'new')
    status = str(row.get('status') or 'n/a')
    band = cost_centers_risk_band(row)
    return DOMAIN_TITLE + ' ' + ident + ' is ' + status + ' (' + band + ').'

def cost_centers_check_cc_code(value: Any) -> list[str]:
    """Field policy for Cc Code inside Cost Centers."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Cc Code is required on Cost Centers.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Cc Code is zero; confirm the Cost Centers case.')
        if number > 9_000_000_000:
            notes.append('Cc Code exceeds the Cost Centers ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Cc Code must be YYYY-MM-DD for Cost Centers.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Cc Code is longer than the Cost Centers ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Cc Code placeholder values are not allowed on Cost Centers.')
    return notes


def cost_centers_normalize_cc_code(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def cost_centers_describe_cc_code() -> str:
    required = 'required' if True else 'optional'
    return 'Cc Code is a ' + required + ' str field on Cost Centers (cost_centers).'


def cost_centers_check_name(value: Any) -> list[str]:
    """Field policy for Name inside Cost Centers."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Name is required on Cost Centers.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Name is zero; confirm the Cost Centers case.')
        if number > 9_000_000_000:
            notes.append('Name exceeds the Cost Centers ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Name must be YYYY-MM-DD for Cost Centers.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Name is longer than the Cost Centers ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Name placeholder values are not allowed on Cost Centers.')
    return notes


def cost_centers_normalize_name(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def cost_centers_describe_name() -> str:
    required = 'required' if True else 'optional'
    return 'Name is a ' + required + ' str field on Cost Centers (cost_centers).'


def cost_centers_check_director(value: Any) -> list[str]:
    """Field policy for Director inside Cost Centers."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Director is required on Cost Centers.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Director is zero; confirm the Cost Centers case.')
        if number > 9_000_000_000:
            notes.append('Director exceeds the Cost Centers ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Director must be YYYY-MM-DD for Cost Centers.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Director is longer than the Cost Centers ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Director placeholder values are not allowed on Cost Centers.')
    return notes


def cost_centers_normalize_director(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def cost_centers_describe_director() -> str:
    required = 'required' if True else 'optional'
    return 'Director is a ' + required + ' str field on Cost Centers (cost_centers).'


def cost_centers_check_headcount(value: Any) -> list[str]:
    """Field policy for Headcount inside Cost Centers."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Headcount is required on Cost Centers.')
        return notes
    if 'int' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Headcount is zero; confirm the Cost Centers case.')
        if number > 9_000_000_000:
            notes.append('Headcount exceeds the Cost Centers ceiling.')
        return notes
    if 'int' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Headcount must be YYYY-MM-DD for Cost Centers.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Headcount is longer than the Cost Centers ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Headcount placeholder values are not allowed on Cost Centers.')
    return notes


def cost_centers_normalize_headcount(value: Any) -> Any:
    if 'int' == 'int':
        return _as_int(value)
    if 'int' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def cost_centers_describe_headcount() -> str:
    required = 'required' if True else 'optional'
    return 'Headcount is a ' + required + ' int field on Cost Centers (cost_centers).'


def cost_centers_check_status(value: Any) -> list[str]:
    """Field policy for Status inside Cost Centers."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Status is required on Cost Centers.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Status is zero; confirm the Cost Centers case.')
        if number > 9_000_000_000:
            notes.append('Status exceeds the Cost Centers ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Status must be YYYY-MM-DD for Cost Centers.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Status is longer than the Cost Centers ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Status placeholder values are not allowed on Cost Centers.')
    return notes


def cost_centers_normalize_status(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def cost_centers_describe_status() -> str:
    required = 'required' if True else 'optional'
    return 'Status is a ' + required + ' str field on Cost Centers (cost_centers).'


FIELD_CHECKS_COST_CENTERS = {
    'cc_code': cost_centers_check_cc_code,
    'name': cost_centers_check_name,
    'director': cost_centers_check_director,
    'headcount': cost_centers_check_headcount,
    'status': cost_centers_check_status,
}


def cost_centers_run_field_checks(row: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for name, checker in FIELD_CHECKS_COST_CENTERS.items():
        found.extend(checker(row.get(name)))
    return found


def cost_centers_policy_card(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'domain': DOMAIN_KEY,
        'title': DOMAIN_TITLE,
        'band': cost_centers_risk_band(row),
        'owner': cost_centers_owner_hint(row),
        'sla_hours': cost_centers_sla_hours(row),
        'exceptions': cost_centers_exception_needed(row),
        'freeze': cost_centers_freeze_window(row),
        'violations': policy.collect(row) + cost_centers_run_field_checks(row),
        'summary': cost_centers_summary_line(row),
    }

