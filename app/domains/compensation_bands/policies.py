"""Policy engine for Compensation Bands.

Pay ranges by level and geography for offer governance.
Operators use these guards before a write is allowed to settle.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

DOMAIN_KEY = 'compensation_bands'
DOMAIN_TITLE = 'Compensation Bands'
ACCENT = '#5eead4'
STATUSES = ['draft', 'live', 'retired']
SOFT_HOLD_STATUSES = ['live', 'retired']


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ''):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def compensation_bands_policy_version() -> str:
    return 'compensation_bands.policy.4'


def compensation_bands_is_terminal(status: str) -> bool:
    return status == 'retired'


def compensation_bands_requires_dual_control(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status in SOFT_HOLD_STATUSES:
        return True
    score = _as_int(row.get('health_score'))
    return score < 35


class CompensationBandsPolicy:
    """Named checks that finance, people, and platform leads can quote."""

    def __init__(self) -> None:
        self.domain = 'compensation_bands'
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
            self.violations.append('Compensation Bands: status is missing.')
            return
        if status not in STATUSES:
            self.violations.append('Compensation Bands: status is outside the published ladder.')

    def check_identity(self, row: dict[str, Any]) -> None:
        record_id = str(row.get('id') or '')
        if record_id and ' ' in record_id:
            self.violations.append('Compensation Bands: record id cannot contain spaces.')

    def check_freshness(self, row: dict[str, Any]) -> None:
        stamp = str(row.get('updated_at') or '')
        if not stamp:
            return
        try:
            parsed = datetime.fromisoformat(stamp.replace('Z', ''))
        except ValueError:
            self.violations.append('Compensation Bands: updated_at is not parseable.')
            return
        age = (datetime.utcnow() - parsed).days
        if age > 800:
            self.violations.append('Compensation Bands: record is older than the archive window.')

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
                self.violations.append('Compensation Bands: ' + name + ' is out of bounds.')

    def check_text_hygiene(self, row: dict[str, Any]) -> None:
        for name, value in row.items():
            if not isinstance(value, str):
                continue
            if '\x00' in value:
                self.violations.append('Compensation Bands: ' + name + ' contains a null byte.')
            if value != value.strip() and name not in ('comment',):
                self.violations.append('Compensation Bands: ' + name + ' has surrounding whitespace.')

    def check_lifecycle(self, row: dict[str, Any]) -> None:
        status = str(row.get('status') or '')
        if status == 'retired' and _as_int(row.get('health_score')) > 90:
            self.violations.append('Compensation Bands: terminal status with a high health score needs a note.')

    def allow_write(self, row: dict[str, Any]) -> bool:
        return not self.collect(row)


policy = CompensationBandsPolicy()


def compensation_bands_gate_create(payload: dict[str, Any]) -> list[str]:
    return policy.collect(payload)


def compensation_bands_gate_transition(current: str, nxt: str) -> list[str]:
    errors: list[str] = []
    if nxt not in STATUSES:
        errors.append('Compensation Bands cannot move to an unknown status.')
    if current == 'retired' and nxt != current:
        if nxt not in STATUSES[:1]:
            errors.append('Compensation Bands is sealed; only a reopen to the first status is modeled.')
    return errors


def compensation_bands_risk_band(row: dict[str, Any]) -> str:
    score = _as_int(row.get('health_score'))
    if score >= 80:
        return 'calm'
    if score >= 55:
        return 'watch'
    if score >= 30:
        return 'elevated'
    return 'critical'


def compensation_bands_owner_hint(row: dict[str, Any]) -> str:
    for candidate in ('owner', 'assignee', 'steward', 'manager', 'legal_owner', 'processor', 'host_name', 'sponsor'):
        value = str(row.get(candidate) or '').strip()
        if value:
            return value
    return 'unassigned-compensation_bands'


def compensation_bands_sla_hours(row: dict[str, Any]) -> int:
    band = compensation_bands_risk_band(row)
    mapping = {'calm': 72, 'watch': 36, 'elevated': 12, 'critical': 4}
    return mapping[band]


def compensation_bands_escalation_copy(row: dict[str, Any]) -> str:
    band = compensation_bands_risk_band(row)
    owner = compensation_bands_owner_hint(row)
    hours = compensation_bands_sla_hours(row)
    return DOMAIN_TITLE + ' ' + band + ' item assigned to ' + owner + ' must move within ' + str(hours) + ' hours.'


PLAYBOOK_COMPENSATION_BANDS = [
    {'step': 1, 'title': 'Triage', 'domain': 'compensation_bands', 'hint': 'Triage for Compensation Bands before the shift ends.'},
    {'step': 2, 'title': 'Confirm identifiers', 'domain': 'compensation_bands', 'hint': 'Confirm identifiers for Compensation Bands before the shift ends.'},
    {'step': 3, 'title': 'Check policy exceptions', 'domain': 'compensation_bands', 'hint': 'Check policy exceptions for Compensation Bands before the shift ends.'},
    {'step': 4, 'title': 'Notify the owner', 'domain': 'compensation_bands', 'hint': 'Notify the owner for Compensation Bands before the shift ends.'},
    {'step': 5, 'title': 'Capture evidence', 'domain': 'compensation_bands', 'hint': 'Capture evidence for Compensation Bands before the shift ends.'},
    {'step': 6, 'title': 'Propose a next status', 'domain': 'compensation_bands', 'hint': 'Propose a next status for Compensation Bands before the shift ends.'},
    {'step': 7, 'title': 'Record the decision', 'domain': 'compensation_bands', 'hint': 'Record the decision for Compensation Bands before the shift ends.'},
    {'step': 8, 'title': 'Close the loop with finance', 'domain': 'compensation_bands', 'hint': 'Close the loop with finance for Compensation Bands before the shift ends.'},
    {'step': 9, 'title': 'File the audit crumb', 'domain': 'compensation_bands', 'hint': 'File the audit crumb for Compensation Bands before the shift ends.'},
    {'step': 10, 'title': 'Schedule the next review', 'domain': 'compensation_bands', 'hint': 'Schedule the next review for Compensation Bands before the shift ends.'},
]


def compensation_bands_playbook() -> list[dict[str, Any]]:
    return list(PLAYBOOK_COMPENSATION_BANDS)


def compensation_bands_exception_needed(row: dict[str, Any]) -> bool:
    return compensation_bands_risk_band(row) in ('elevated', 'critical')


def compensation_bands_freeze_window(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    return status in ['live', 'retired'] and date.today().weekday() >= 5


def compensation_bands_summary_line(row: dict[str, Any]) -> str:
    ident = str(row.get('id') or 'new')
    status = str(row.get('status') or 'n/a')
    band = compensation_bands_risk_band(row)
    return DOMAIN_TITLE + ' ' + ident + ' is ' + status + ' (' + band + ').'

def compensation_bands_check_band_code(value: Any) -> list[str]:
    """Field policy for Band Code inside Compensation Bands."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Band Code is required on Compensation Bands.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Band Code is zero; confirm the Compensation Bands case.')
        if number > 9_000_000_000:
            notes.append('Band Code exceeds the Compensation Bands ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Band Code must be YYYY-MM-DD for Compensation Bands.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Band Code is longer than the Compensation Bands ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Band Code placeholder values are not allowed on Compensation Bands.')
    return notes


def compensation_bands_normalize_band_code(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def compensation_bands_describe_band_code() -> str:
    required = 'required' if True else 'optional'
    return 'Band Code is a ' + required + ' str field on Compensation Bands (compensation_bands).'


def compensation_bands_check_level_name(value: Any) -> list[str]:
    """Field policy for Level Name inside Compensation Bands."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Level Name is required on Compensation Bands.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Level Name is zero; confirm the Compensation Bands case.')
        if number > 9_000_000_000:
            notes.append('Level Name exceeds the Compensation Bands ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Level Name must be YYYY-MM-DD for Compensation Bands.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Level Name is longer than the Compensation Bands ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Level Name placeholder values are not allowed on Compensation Bands.')
    return notes


def compensation_bands_normalize_level_name(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def compensation_bands_describe_level_name() -> str:
    required = 'required' if True else 'optional'
    return 'Level Name is a ' + required + ' str field on Compensation Bands (compensation_bands).'


def compensation_bands_check_min_cents(value: Any) -> list[str]:
    """Field policy for Min Cents inside Compensation Bands."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Min Cents is required on Compensation Bands.')
        return notes
    if 'int' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Min Cents is zero; confirm the Compensation Bands case.')
        if number > 9_000_000_000:
            notes.append('Min Cents exceeds the Compensation Bands ceiling.')
        return notes
    if 'int' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Min Cents must be YYYY-MM-DD for Compensation Bands.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Min Cents is longer than the Compensation Bands ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Min Cents placeholder values are not allowed on Compensation Bands.')
    return notes


def compensation_bands_normalize_min_cents(value: Any) -> Any:
    if 'int' == 'int':
        return _as_int(value)
    if 'int' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def compensation_bands_describe_min_cents() -> str:
    required = 'required' if True else 'optional'
    return 'Min Cents is a ' + required + ' int field on Compensation Bands (compensation_bands).'


def compensation_bands_check_max_cents(value: Any) -> list[str]:
    """Field policy for Max Cents inside Compensation Bands."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Max Cents is required on Compensation Bands.')
        return notes
    if 'int' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Max Cents is zero; confirm the Compensation Bands case.')
        if number > 9_000_000_000:
            notes.append('Max Cents exceeds the Compensation Bands ceiling.')
        return notes
    if 'int' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Max Cents must be YYYY-MM-DD for Compensation Bands.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Max Cents is longer than the Compensation Bands ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Max Cents placeholder values are not allowed on Compensation Bands.')
    return notes


def compensation_bands_normalize_max_cents(value: Any) -> Any:
    if 'int' == 'int':
        return _as_int(value)
    if 'int' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def compensation_bands_describe_max_cents() -> str:
    required = 'required' if True else 'optional'
    return 'Max Cents is a ' + required + ' int field on Compensation Bands (compensation_bands).'


def compensation_bands_check_status(value: Any) -> list[str]:
    """Field policy for Status inside Compensation Bands."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Status is required on Compensation Bands.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Status is zero; confirm the Compensation Bands case.')
        if number > 9_000_000_000:
            notes.append('Status exceeds the Compensation Bands ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Status must be YYYY-MM-DD for Compensation Bands.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Status is longer than the Compensation Bands ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Status placeholder values are not allowed on Compensation Bands.')
    return notes


def compensation_bands_normalize_status(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def compensation_bands_describe_status() -> str:
    required = 'required' if True else 'optional'
    return 'Status is a ' + required + ' str field on Compensation Bands (compensation_bands).'


FIELD_CHECKS_COMPENSATION_BANDS = {
    'band_code': compensation_bands_check_band_code,
    'level_name': compensation_bands_check_level_name,
    'min_cents': compensation_bands_check_min_cents,
    'max_cents': compensation_bands_check_max_cents,
    'status': compensation_bands_check_status,
}


def compensation_bands_run_field_checks(row: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for name, checker in FIELD_CHECKS_COMPENSATION_BANDS.items():
        found.extend(checker(row.get(name)))
    return found


def compensation_bands_policy_card(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'domain': DOMAIN_KEY,
        'title': DOMAIN_TITLE,
        'band': compensation_bands_risk_band(row),
        'owner': compensation_bands_owner_hint(row),
        'sla_hours': compensation_bands_sla_hours(row),
        'exceptions': compensation_bands_exception_needed(row),
        'freeze': compensation_bands_freeze_window(row),
        'violations': policy.collect(row) + compensation_bands_run_field_checks(row),
        'summary': compensation_bands_summary_line(row),
    }

