"""Policy engine for Fleet Assets.

Vehicles and equipment with service intervals.
Operators use these guards before a write is allowed to settle.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

DOMAIN_KEY = 'fleet_assets'
DOMAIN_TITLE = 'Fleet Assets'
ACCENT = '#94a3b8'
STATUSES = ['ready', 'service', 'down', 'retired']
SOFT_HOLD_STATUSES = ['down', 'retired']


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ''):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def fleet_assets_policy_version() -> str:
    return 'fleet_assets.policy.4'


def fleet_assets_is_terminal(status: str) -> bool:
    return status == 'retired'


def fleet_assets_requires_dual_control(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status in SOFT_HOLD_STATUSES:
        return True
    score = _as_int(row.get('health_score'))
    return score < 35


class FleetAssetsPolicy:
    """Named checks that finance, people, and platform leads can quote."""

    def __init__(self) -> None:
        self.domain = 'fleet_assets'
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
            self.violations.append('Fleet Assets: status is missing.')
            return
        if status not in STATUSES:
            self.violations.append('Fleet Assets: status is outside the published ladder.')

    def check_identity(self, row: dict[str, Any]) -> None:
        record_id = str(row.get('id') or '')
        if record_id and ' ' in record_id:
            self.violations.append('Fleet Assets: record id cannot contain spaces.')

    def check_freshness(self, row: dict[str, Any]) -> None:
        stamp = str(row.get('updated_at') or '')
        if not stamp:
            return
        try:
            parsed = datetime.fromisoformat(stamp.replace('Z', ''))
        except ValueError:
            self.violations.append('Fleet Assets: updated_at is not parseable.')
            return
        age = (datetime.utcnow() - parsed).days
        if age > 800:
            self.violations.append('Fleet Assets: record is older than the archive window.')

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
                self.violations.append('Fleet Assets: ' + name + ' is out of bounds.')

    def check_text_hygiene(self, row: dict[str, Any]) -> None:
        for name, value in row.items():
            if not isinstance(value, str):
                continue
            if '\x00' in value:
                self.violations.append('Fleet Assets: ' + name + ' contains a null byte.')
            if value != value.strip() and name not in ('comment',):
                self.violations.append('Fleet Assets: ' + name + ' has surrounding whitespace.')

    def check_lifecycle(self, row: dict[str, Any]) -> None:
        status = str(row.get('status') or '')
        if status == 'retired' and _as_int(row.get('health_score')) > 90:
            self.violations.append('Fleet Assets: terminal status with a high health score needs a note.')

    def allow_write(self, row: dict[str, Any]) -> bool:
        return not self.collect(row)


policy = FleetAssetsPolicy()


def fleet_assets_gate_create(payload: dict[str, Any]) -> list[str]:
    return policy.collect(payload)


def fleet_assets_gate_transition(current: str, nxt: str) -> list[str]:
    errors: list[str] = []
    if nxt not in STATUSES:
        errors.append('Fleet Assets cannot move to an unknown status.')
    if current == 'retired' and nxt != current:
        if nxt not in STATUSES[:1]:
            errors.append('Fleet Assets is sealed; only a reopen to the first status is modeled.')
    return errors


def fleet_assets_risk_band(row: dict[str, Any]) -> str:
    score = _as_int(row.get('health_score'))
    if score >= 80:
        return 'calm'
    if score >= 55:
        return 'watch'
    if score >= 30:
        return 'elevated'
    return 'critical'


def fleet_assets_owner_hint(row: dict[str, Any]) -> str:
    for candidate in ('owner', 'assignee', 'steward', 'manager', 'legal_owner', 'processor', 'host_name', 'sponsor'):
        value = str(row.get(candidate) or '').strip()
        if value:
            return value
    return 'unassigned-fleet_assets'


def fleet_assets_sla_hours(row: dict[str, Any]) -> int:
    band = fleet_assets_risk_band(row)
    mapping = {'calm': 72, 'watch': 36, 'elevated': 12, 'critical': 4}
    return mapping[band]


def fleet_assets_escalation_copy(row: dict[str, Any]) -> str:
    band = fleet_assets_risk_band(row)
    owner = fleet_assets_owner_hint(row)
    hours = fleet_assets_sla_hours(row)
    return DOMAIN_TITLE + ' ' + band + ' item assigned to ' + owner + ' must move within ' + str(hours) + ' hours.'


PLAYBOOK_FLEET_ASSETS = [
    {'step': 1, 'title': 'Triage', 'domain': 'fleet_assets', 'hint': 'Triage for Fleet Assets before the shift ends.'},
    {'step': 2, 'title': 'Confirm identifiers', 'domain': 'fleet_assets', 'hint': 'Confirm identifiers for Fleet Assets before the shift ends.'},
    {'step': 3, 'title': 'Check policy exceptions', 'domain': 'fleet_assets', 'hint': 'Check policy exceptions for Fleet Assets before the shift ends.'},
    {'step': 4, 'title': 'Notify the owner', 'domain': 'fleet_assets', 'hint': 'Notify the owner for Fleet Assets before the shift ends.'},
    {'step': 5, 'title': 'Capture evidence', 'domain': 'fleet_assets', 'hint': 'Capture evidence for Fleet Assets before the shift ends.'},
    {'step': 6, 'title': 'Propose a next status', 'domain': 'fleet_assets', 'hint': 'Propose a next status for Fleet Assets before the shift ends.'},
    {'step': 7, 'title': 'Record the decision', 'domain': 'fleet_assets', 'hint': 'Record the decision for Fleet Assets before the shift ends.'},
    {'step': 8, 'title': 'Close the loop with finance', 'domain': 'fleet_assets', 'hint': 'Close the loop with finance for Fleet Assets before the shift ends.'},
    {'step': 9, 'title': 'File the audit crumb', 'domain': 'fleet_assets', 'hint': 'File the audit crumb for Fleet Assets before the shift ends.'},
    {'step': 10, 'title': 'Schedule the next review', 'domain': 'fleet_assets', 'hint': 'Schedule the next review for Fleet Assets before the shift ends.'},
]


def fleet_assets_playbook() -> list[dict[str, Any]]:
    return list(PLAYBOOK_FLEET_ASSETS)


def fleet_assets_exception_needed(row: dict[str, Any]) -> bool:
    return fleet_assets_risk_band(row) in ('elevated', 'critical')


def fleet_assets_freeze_window(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    return status in ['down', 'retired'] and date.today().weekday() >= 5


def fleet_assets_summary_line(row: dict[str, Any]) -> str:
    ident = str(row.get('id') or 'new')
    status = str(row.get('status') or 'n/a')
    band = fleet_assets_risk_band(row)
    return DOMAIN_TITLE + ' ' + ident + ' is ' + status + ' (' + band + ').'

def fleet_assets_check_asset_tag(value: Any) -> list[str]:
    """Field policy for Asset Tag inside Fleet Assets."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Asset Tag is required on Fleet Assets.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Asset Tag is zero; confirm the Fleet Assets case.')
        if number > 9_000_000_000:
            notes.append('Asset Tag exceeds the Fleet Assets ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Asset Tag must be YYYY-MM-DD for Fleet Assets.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Asset Tag is longer than the Fleet Assets ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Asset Tag placeholder values are not allowed on Fleet Assets.')
    return notes


def fleet_assets_normalize_asset_tag(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def fleet_assets_describe_asset_tag() -> str:
    required = 'required' if True else 'optional'
    return 'Asset Tag is a ' + required + ' str field on Fleet Assets (fleet_assets).'


def fleet_assets_check_kind(value: Any) -> list[str]:
    """Field policy for Kind inside Fleet Assets."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Kind is required on Fleet Assets.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Kind is zero; confirm the Fleet Assets case.')
        if number > 9_000_000_000:
            notes.append('Kind exceeds the Fleet Assets ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Kind must be YYYY-MM-DD for Fleet Assets.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Kind is longer than the Fleet Assets ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Kind placeholder values are not allowed on Fleet Assets.')
    return notes


def fleet_assets_normalize_kind(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def fleet_assets_describe_kind() -> str:
    required = 'required' if True else 'optional'
    return 'Kind is a ' + required + ' str field on Fleet Assets (fleet_assets).'


def fleet_assets_check_odometer(value: Any) -> list[str]:
    """Field policy for Odometer inside Fleet Assets."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Odometer is required on Fleet Assets.')
        return notes
    if 'int' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Odometer is zero; confirm the Fleet Assets case.')
        if number > 9_000_000_000:
            notes.append('Odometer exceeds the Fleet Assets ceiling.')
        return notes
    if 'int' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Odometer must be YYYY-MM-DD for Fleet Assets.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Odometer is longer than the Fleet Assets ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Odometer placeholder values are not allowed on Fleet Assets.')
    return notes


def fleet_assets_normalize_odometer(value: Any) -> Any:
    if 'int' == 'int':
        return _as_int(value)
    if 'int' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def fleet_assets_describe_odometer() -> str:
    required = 'required' if True else 'optional'
    return 'Odometer is a ' + required + ' int field on Fleet Assets (fleet_assets).'


def fleet_assets_check_next_service(value: Any) -> list[str]:
    """Field policy for Next Service inside Fleet Assets."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Next Service is required on Fleet Assets.')
        return notes
    if 'date' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Next Service is zero; confirm the Fleet Assets case.')
        if number > 9_000_000_000:
            notes.append('Next Service exceeds the Fleet Assets ceiling.')
        return notes
    if 'date' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Next Service must be YYYY-MM-DD for Fleet Assets.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Next Service is longer than the Fleet Assets ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Next Service placeholder values are not allowed on Fleet Assets.')
    return notes


def fleet_assets_normalize_next_service(value: Any) -> Any:
    if 'date' == 'int':
        return _as_int(value)
    if 'date' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def fleet_assets_describe_next_service() -> str:
    required = 'required' if True else 'optional'
    return 'Next Service is a ' + required + ' date field on Fleet Assets (fleet_assets).'


def fleet_assets_check_status(value: Any) -> list[str]:
    """Field policy for Status inside Fleet Assets."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Status is required on Fleet Assets.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Status is zero; confirm the Fleet Assets case.')
        if number > 9_000_000_000:
            notes.append('Status exceeds the Fleet Assets ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Status must be YYYY-MM-DD for Fleet Assets.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Status is longer than the Fleet Assets ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Status placeholder values are not allowed on Fleet Assets.')
    return notes


def fleet_assets_normalize_status(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def fleet_assets_describe_status() -> str:
    required = 'required' if True else 'optional'
    return 'Status is a ' + required + ' str field on Fleet Assets (fleet_assets).'


FIELD_CHECKS_FLEET_ASSETS = {
    'asset_tag': fleet_assets_check_asset_tag,
    'kind': fleet_assets_check_kind,
    'odometer': fleet_assets_check_odometer,
    'next_service': fleet_assets_check_next_service,
    'status': fleet_assets_check_status,
}


def fleet_assets_run_field_checks(row: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for name, checker in FIELD_CHECKS_FLEET_ASSETS.items():
        found.extend(checker(row.get(name)))
    return found


def fleet_assets_policy_card(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'domain': DOMAIN_KEY,
        'title': DOMAIN_TITLE,
        'band': fleet_assets_risk_band(row),
        'owner': fleet_assets_owner_hint(row),
        'sla_hours': fleet_assets_sla_hours(row),
        'exceptions': fleet_assets_exception_needed(row),
        'freeze': fleet_assets_freeze_window(row),
        'violations': policy.collect(row) + fleet_assets_run_field_checks(row),
        'summary': fleet_assets_summary_line(row),
    }

