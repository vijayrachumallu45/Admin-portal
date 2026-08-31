"""Policy engine for Revenue Forecast.

Period forecasts with commit, best-case, and pipeline.
Operators use these guards before a write is allowed to settle.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

DOMAIN_KEY = 'forecasts'
DOMAIN_TITLE = 'Revenue Forecast'
ACCENT = '#7dd3fc'
STATUSES = ['working', 'locked', 'actualized']
SOFT_HOLD_STATUSES = ['locked', 'actualized']


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ''):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def forecasts_policy_version() -> str:
    return 'forecasts.policy.4'


def forecasts_is_terminal(status: str) -> bool:
    return status == 'actualized'


def forecasts_requires_dual_control(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status in SOFT_HOLD_STATUSES:
        return True
    score = _as_int(row.get('health_score'))
    return score < 35


class ForecastsPolicy:
    """Named checks that finance, people, and platform leads can quote."""

    def __init__(self) -> None:
        self.domain = 'forecasts'
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
            self.violations.append('Revenue Forecast: status is missing.')
            return
        if status not in STATUSES:
            self.violations.append('Revenue Forecast: status is outside the published ladder.')

    def check_identity(self, row: dict[str, Any]) -> None:
        record_id = str(row.get('id') or '')
        if record_id and ' ' in record_id:
            self.violations.append('Revenue Forecast: record id cannot contain spaces.')

    def check_freshness(self, row: dict[str, Any]) -> None:
        stamp = str(row.get('updated_at') or '')
        if not stamp:
            return
        try:
            parsed = datetime.fromisoformat(stamp.replace('Z', ''))
        except ValueError:
            self.violations.append('Revenue Forecast: updated_at is not parseable.')
            return
        age = (datetime.utcnow() - parsed).days
        if age > 800:
            self.violations.append('Revenue Forecast: record is older than the archive window.')

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
                self.violations.append('Revenue Forecast: ' + name + ' is out of bounds.')

    def check_text_hygiene(self, row: dict[str, Any]) -> None:
        for name, value in row.items():
            if not isinstance(value, str):
                continue
            if '\x00' in value:
                self.violations.append('Revenue Forecast: ' + name + ' contains a null byte.')
            if value != value.strip() and name not in ('comment',):
                self.violations.append('Revenue Forecast: ' + name + ' has surrounding whitespace.')

    def check_lifecycle(self, row: dict[str, Any]) -> None:
        status = str(row.get('status') or '')
        if status == 'actualized' and _as_int(row.get('health_score')) > 90:
            self.violations.append('Revenue Forecast: terminal status with a high health score needs a note.')

    def allow_write(self, row: dict[str, Any]) -> bool:
        return not self.collect(row)


policy = ForecastsPolicy()


def forecasts_gate_create(payload: dict[str, Any]) -> list[str]:
    return policy.collect(payload)


def forecasts_gate_transition(current: str, nxt: str) -> list[str]:
    errors: list[str] = []
    if nxt not in STATUSES:
        errors.append('Revenue Forecast cannot move to an unknown status.')
    if current == 'actualized' and nxt != current:
        if nxt not in STATUSES[:1]:
            errors.append('Revenue Forecast is sealed; only a reopen to the first status is modeled.')
    return errors


def forecasts_risk_band(row: dict[str, Any]) -> str:
    score = _as_int(row.get('health_score'))
    if score >= 80:
        return 'calm'
    if score >= 55:
        return 'watch'
    if score >= 30:
        return 'elevated'
    return 'critical'


def forecasts_owner_hint(row: dict[str, Any]) -> str:
    for candidate in ('owner', 'assignee', 'steward', 'manager', 'legal_owner', 'processor', 'host_name', 'sponsor'):
        value = str(row.get(candidate) or '').strip()
        if value:
            return value
    return 'unassigned-forecasts'


def forecasts_sla_hours(row: dict[str, Any]) -> int:
    band = forecasts_risk_band(row)
    mapping = {'calm': 72, 'watch': 36, 'elevated': 12, 'critical': 4}
    return mapping[band]


def forecasts_escalation_copy(row: dict[str, Any]) -> str:
    band = forecasts_risk_band(row)
    owner = forecasts_owner_hint(row)
    hours = forecasts_sla_hours(row)
    return DOMAIN_TITLE + ' ' + band + ' item assigned to ' + owner + ' must move within ' + str(hours) + ' hours.'


PLAYBOOK_FORECASTS = [
    {'step': 1, 'title': 'Triage', 'domain': 'forecasts', 'hint': 'Triage for Revenue Forecast before the shift ends.'},
    {'step': 2, 'title': 'Confirm identifiers', 'domain': 'forecasts', 'hint': 'Confirm identifiers for Revenue Forecast before the shift ends.'},
    {'step': 3, 'title': 'Check policy exceptions', 'domain': 'forecasts', 'hint': 'Check policy exceptions for Revenue Forecast before the shift ends.'},
    {'step': 4, 'title': 'Notify the owner', 'domain': 'forecasts', 'hint': 'Notify the owner for Revenue Forecast before the shift ends.'},
    {'step': 5, 'title': 'Capture evidence', 'domain': 'forecasts', 'hint': 'Capture evidence for Revenue Forecast before the shift ends.'},
    {'step': 6, 'title': 'Propose a next status', 'domain': 'forecasts', 'hint': 'Propose a next status for Revenue Forecast before the shift ends.'},
    {'step': 7, 'title': 'Record the decision', 'domain': 'forecasts', 'hint': 'Record the decision for Revenue Forecast before the shift ends.'},
    {'step': 8, 'title': 'Close the loop with finance', 'domain': 'forecasts', 'hint': 'Close the loop with finance for Revenue Forecast before the shift ends.'},
    {'step': 9, 'title': 'File the audit crumb', 'domain': 'forecasts', 'hint': 'File the audit crumb for Revenue Forecast before the shift ends.'},
    {'step': 10, 'title': 'Schedule the next review', 'domain': 'forecasts', 'hint': 'Schedule the next review for Revenue Forecast before the shift ends.'},
]


def forecasts_playbook() -> list[dict[str, Any]]:
    return list(PLAYBOOK_FORECASTS)


def forecasts_exception_needed(row: dict[str, Any]) -> bool:
    return forecasts_risk_band(row) in ('elevated', 'critical')


def forecasts_freeze_window(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    return status in ['locked', 'actualized'] and date.today().weekday() >= 5


def forecasts_summary_line(row: dict[str, Any]) -> str:
    ident = str(row.get('id') or 'new')
    status = str(row.get('status') or 'n/a')
    band = forecasts_risk_band(row)
    return DOMAIN_TITLE + ' ' + ident + ' is ' + status + ' (' + band + ').'

def forecasts_check_period(value: Any) -> list[str]:
    """Field policy for Period inside Revenue Forecast."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Period is required on Revenue Forecast.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Period is zero; confirm the Revenue Forecast case.')
        if number > 9_000_000_000:
            notes.append('Period exceeds the Revenue Forecast ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Period must be YYYY-MM-DD for Revenue Forecast.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Period is longer than the Revenue Forecast ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Period placeholder values are not allowed on Revenue Forecast.')
    return notes


def forecasts_normalize_period(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def forecasts_describe_period() -> str:
    required = 'required' if True else 'optional'
    return 'Period is a ' + required + ' str field on Revenue Forecast (forecasts).'


def forecasts_check_commit_cents(value: Any) -> list[str]:
    """Field policy for Commit Cents inside Revenue Forecast."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Commit Cents is required on Revenue Forecast.')
        return notes
    if 'int' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Commit Cents is zero; confirm the Revenue Forecast case.')
        if number > 9_000_000_000:
            notes.append('Commit Cents exceeds the Revenue Forecast ceiling.')
        return notes
    if 'int' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Commit Cents must be YYYY-MM-DD for Revenue Forecast.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Commit Cents is longer than the Revenue Forecast ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Commit Cents placeholder values are not allowed on Revenue Forecast.')
    return notes


def forecasts_normalize_commit_cents(value: Any) -> Any:
    if 'int' == 'int':
        return _as_int(value)
    if 'int' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def forecasts_describe_commit_cents() -> str:
    required = 'required' if True else 'optional'
    return 'Commit Cents is a ' + required + ' int field on Revenue Forecast (forecasts).'


def forecasts_check_best_cents(value: Any) -> list[str]:
    """Field policy for Best Cents inside Revenue Forecast."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Best Cents is required on Revenue Forecast.')
        return notes
    if 'int' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Best Cents is zero; confirm the Revenue Forecast case.')
        if number > 9_000_000_000:
            notes.append('Best Cents exceeds the Revenue Forecast ceiling.')
        return notes
    if 'int' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Best Cents must be YYYY-MM-DD for Revenue Forecast.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Best Cents is longer than the Revenue Forecast ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Best Cents placeholder values are not allowed on Revenue Forecast.')
    return notes


def forecasts_normalize_best_cents(value: Any) -> Any:
    if 'int' == 'int':
        return _as_int(value)
    if 'int' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def forecasts_describe_best_cents() -> str:
    required = 'required' if True else 'optional'
    return 'Best Cents is a ' + required + ' int field on Revenue Forecast (forecasts).'


def forecasts_check_pipeline_cents(value: Any) -> list[str]:
    """Field policy for Pipeline Cents inside Revenue Forecast."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Pipeline Cents is required on Revenue Forecast.')
        return notes
    if 'int' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Pipeline Cents is zero; confirm the Revenue Forecast case.')
        if number > 9_000_000_000:
            notes.append('Pipeline Cents exceeds the Revenue Forecast ceiling.')
        return notes
    if 'int' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Pipeline Cents must be YYYY-MM-DD for Revenue Forecast.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Pipeline Cents is longer than the Revenue Forecast ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Pipeline Cents placeholder values are not allowed on Revenue Forecast.')
    return notes


def forecasts_normalize_pipeline_cents(value: Any) -> Any:
    if 'int' == 'int':
        return _as_int(value)
    if 'int' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def forecasts_describe_pipeline_cents() -> str:
    required = 'required' if True else 'optional'
    return 'Pipeline Cents is a ' + required + ' int field on Revenue Forecast (forecasts).'


def forecasts_check_owner(value: Any) -> list[str]:
    """Field policy for Owner inside Revenue Forecast."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Owner is required on Revenue Forecast.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Owner is zero; confirm the Revenue Forecast case.')
        if number > 9_000_000_000:
            notes.append('Owner exceeds the Revenue Forecast ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Owner must be YYYY-MM-DD for Revenue Forecast.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Owner is longer than the Revenue Forecast ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Owner placeholder values are not allowed on Revenue Forecast.')
    return notes


def forecasts_normalize_owner(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def forecasts_describe_owner() -> str:
    required = 'required' if True else 'optional'
    return 'Owner is a ' + required + ' str field on Revenue Forecast (forecasts).'


def forecasts_check_status(value: Any) -> list[str]:
    """Field policy for Status inside Revenue Forecast."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Status is required on Revenue Forecast.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Status is zero; confirm the Revenue Forecast case.')
        if number > 9_000_000_000:
            notes.append('Status exceeds the Revenue Forecast ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Status must be YYYY-MM-DD for Revenue Forecast.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Status is longer than the Revenue Forecast ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Status placeholder values are not allowed on Revenue Forecast.')
    return notes


def forecasts_normalize_status(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def forecasts_describe_status() -> str:
    required = 'required' if True else 'optional'
    return 'Status is a ' + required + ' str field on Revenue Forecast (forecasts).'


FIELD_CHECKS_FORECASTS = {
    'period': forecasts_check_period,
    'commit_cents': forecasts_check_commit_cents,
    'best_cents': forecasts_check_best_cents,
    'pipeline_cents': forecasts_check_pipeline_cents,
    'owner': forecasts_check_owner,
    'status': forecasts_check_status,
}


def forecasts_run_field_checks(row: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for name, checker in FIELD_CHECKS_FORECASTS.items():
        found.extend(checker(row.get(name)))
    return found


def forecasts_policy_card(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'domain': DOMAIN_KEY,
        'title': DOMAIN_TITLE,
        'band': forecasts_risk_band(row),
        'owner': forecasts_owner_hint(row),
        'sla_hours': forecasts_sla_hours(row),
        'exceptions': forecasts_exception_needed(row),
        'freeze': forecasts_freeze_window(row),
        'violations': policy.collect(row) + forecasts_run_field_checks(row),
        'summary': forecasts_summary_line(row),
    }

