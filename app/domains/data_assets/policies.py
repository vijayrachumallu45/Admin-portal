"""Policy engine for Data Catalog.

Datasets, stewards, and classification labels.
Operators use these guards before a write is allowed to settle.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

DOMAIN_KEY = 'data_assets'
DOMAIN_TITLE = 'Data Catalog'
ACCENT = '#a5b4fc'
STATUSES = ['candidate', 'certified', 'restricted', 'archived']
SOFT_HOLD_STATUSES = ['restricted', 'archived']


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ''):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def data_assets_policy_version() -> str:
    return 'data_assets.policy.4'


def data_assets_is_terminal(status: str) -> bool:
    return status == 'archived'


def data_assets_requires_dual_control(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status in SOFT_HOLD_STATUSES:
        return True
    score = _as_int(row.get('health_score'))
    return score < 35


class DataAssetsPolicy:
    """Named checks that finance, people, and platform leads can quote."""

    def __init__(self) -> None:
        self.domain = 'data_assets'
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
            self.violations.append('Data Catalog: status is missing.')
            return
        if status not in STATUSES:
            self.violations.append('Data Catalog: status is outside the published ladder.')

    def check_identity(self, row: dict[str, Any]) -> None:
        record_id = str(row.get('id') or '')
        if record_id and ' ' in record_id:
            self.violations.append('Data Catalog: record id cannot contain spaces.')

    def check_freshness(self, row: dict[str, Any]) -> None:
        stamp = str(row.get('updated_at') or '')
        if not stamp:
            return
        try:
            parsed = datetime.fromisoformat(stamp.replace('Z', ''))
        except ValueError:
            self.violations.append('Data Catalog: updated_at is not parseable.')
            return
        age = (datetime.utcnow() - parsed).days
        if age > 800:
            self.violations.append('Data Catalog: record is older than the archive window.')

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
                self.violations.append('Data Catalog: ' + name + ' is out of bounds.')

    def check_text_hygiene(self, row: dict[str, Any]) -> None:
        for name, value in row.items():
            if not isinstance(value, str):
                continue
            if '\x00' in value:
                self.violations.append('Data Catalog: ' + name + ' contains a null byte.')
            if value != value.strip() and name not in ('comment',):
                self.violations.append('Data Catalog: ' + name + ' has surrounding whitespace.')

    def check_lifecycle(self, row: dict[str, Any]) -> None:
        status = str(row.get('status') or '')
        if status == 'archived' and _as_int(row.get('health_score')) > 90:
            self.violations.append('Data Catalog: terminal status with a high health score needs a note.')

    def allow_write(self, row: dict[str, Any]) -> bool:
        return not self.collect(row)


policy = DataAssetsPolicy()


def data_assets_gate_create(payload: dict[str, Any]) -> list[str]:
    return policy.collect(payload)


def data_assets_gate_transition(current: str, nxt: str) -> list[str]:
    errors: list[str] = []
    if nxt not in STATUSES:
        errors.append('Data Catalog cannot move to an unknown status.')
    if current == 'archived' and nxt != current:
        if nxt not in STATUSES[:1]:
            errors.append('Data Catalog is sealed; only a reopen to the first status is modeled.')
    return errors


def data_assets_risk_band(row: dict[str, Any]) -> str:
    score = _as_int(row.get('health_score'))
    if score >= 80:
        return 'calm'
    if score >= 55:
        return 'watch'
    if score >= 30:
        return 'elevated'
    return 'critical'


def data_assets_owner_hint(row: dict[str, Any]) -> str:
    for candidate in ('owner', 'assignee', 'steward', 'manager', 'legal_owner', 'processor', 'host_name', 'sponsor'):
        value = str(row.get(candidate) or '').strip()
        if value:
            return value
    return 'unassigned-data_assets'


def data_assets_sla_hours(row: dict[str, Any]) -> int:
    band = data_assets_risk_band(row)
    mapping = {'calm': 72, 'watch': 36, 'elevated': 12, 'critical': 4}
    return mapping[band]


def data_assets_escalation_copy(row: dict[str, Any]) -> str:
    band = data_assets_risk_band(row)
    owner = data_assets_owner_hint(row)
    hours = data_assets_sla_hours(row)
    return DOMAIN_TITLE + ' ' + band + ' item assigned to ' + owner + ' must move within ' + str(hours) + ' hours.'


PLAYBOOK_DATA_ASSETS = [
    {'step': 1, 'title': 'Triage', 'domain': 'data_assets', 'hint': 'Triage for Data Catalog before the shift ends.'},
    {'step': 2, 'title': 'Confirm identifiers', 'domain': 'data_assets', 'hint': 'Confirm identifiers for Data Catalog before the shift ends.'},
    {'step': 3, 'title': 'Check policy exceptions', 'domain': 'data_assets', 'hint': 'Check policy exceptions for Data Catalog before the shift ends.'},
    {'step': 4, 'title': 'Notify the owner', 'domain': 'data_assets', 'hint': 'Notify the owner for Data Catalog before the shift ends.'},
    {'step': 5, 'title': 'Capture evidence', 'domain': 'data_assets', 'hint': 'Capture evidence for Data Catalog before the shift ends.'},
    {'step': 6, 'title': 'Propose a next status', 'domain': 'data_assets', 'hint': 'Propose a next status for Data Catalog before the shift ends.'},
    {'step': 7, 'title': 'Record the decision', 'domain': 'data_assets', 'hint': 'Record the decision for Data Catalog before the shift ends.'},
    {'step': 8, 'title': 'Close the loop with finance', 'domain': 'data_assets', 'hint': 'Close the loop with finance for Data Catalog before the shift ends.'},
    {'step': 9, 'title': 'File the audit crumb', 'domain': 'data_assets', 'hint': 'File the audit crumb for Data Catalog before the shift ends.'},
    {'step': 10, 'title': 'Schedule the next review', 'domain': 'data_assets', 'hint': 'Schedule the next review for Data Catalog before the shift ends.'},
]


def data_assets_playbook() -> list[dict[str, Any]]:
    return list(PLAYBOOK_DATA_ASSETS)


def data_assets_exception_needed(row: dict[str, Any]) -> bool:
    return data_assets_risk_band(row) in ('elevated', 'critical')


def data_assets_freeze_window(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    return status in ['restricted', 'archived'] and date.today().weekday() >= 5


def data_assets_summary_line(row: dict[str, Any]) -> str:
    ident = str(row.get('id') or 'new')
    status = str(row.get('status') or 'n/a')
    band = data_assets_risk_band(row)
    return DOMAIN_TITLE + ' ' + ident + ' is ' + status + ' (' + band + ').'

def data_assets_check_asset_key(value: Any) -> list[str]:
    """Field policy for Asset Key inside Data Catalog."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Asset Key is required on Data Catalog.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Asset Key is zero; confirm the Data Catalog case.')
        if number > 9_000_000_000:
            notes.append('Asset Key exceeds the Data Catalog ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Asset Key must be YYYY-MM-DD for Data Catalog.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Asset Key is longer than the Data Catalog ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Asset Key placeholder values are not allowed on Data Catalog.')
    return notes


def data_assets_normalize_asset_key(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def data_assets_describe_asset_key() -> str:
    required = 'required' if True else 'optional'
    return 'Asset Key is a ' + required + ' str field on Data Catalog (data_assets).'


def data_assets_check_system_name(value: Any) -> list[str]:
    """Field policy for System Name inside Data Catalog."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('System Name is required on Data Catalog.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('System Name is zero; confirm the Data Catalog case.')
        if number > 9_000_000_000:
            notes.append('System Name exceeds the Data Catalog ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('System Name must be YYYY-MM-DD for Data Catalog.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('System Name is longer than the Data Catalog ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('System Name placeholder values are not allowed on Data Catalog.')
    return notes


def data_assets_normalize_system_name(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def data_assets_describe_system_name() -> str:
    required = 'required' if True else 'optional'
    return 'System Name is a ' + required + ' str field on Data Catalog (data_assets).'


def data_assets_check_classification(value: Any) -> list[str]:
    """Field policy for Classification inside Data Catalog."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Classification is required on Data Catalog.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Classification is zero; confirm the Data Catalog case.')
        if number > 9_000_000_000:
            notes.append('Classification exceeds the Data Catalog ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Classification must be YYYY-MM-DD for Data Catalog.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Classification is longer than the Data Catalog ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Classification placeholder values are not allowed on Data Catalog.')
    return notes


def data_assets_normalize_classification(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def data_assets_describe_classification() -> str:
    required = 'required' if True else 'optional'
    return 'Classification is a ' + required + ' str field on Data Catalog (data_assets).'


def data_assets_check_steward(value: Any) -> list[str]:
    """Field policy for Steward inside Data Catalog."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Steward is required on Data Catalog.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Steward is zero; confirm the Data Catalog case.')
        if number > 9_000_000_000:
            notes.append('Steward exceeds the Data Catalog ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Steward must be YYYY-MM-DD for Data Catalog.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Steward is longer than the Data Catalog ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Steward placeholder values are not allowed on Data Catalog.')
    return notes


def data_assets_normalize_steward(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def data_assets_describe_steward() -> str:
    required = 'required' if True else 'optional'
    return 'Steward is a ' + required + ' str field on Data Catalog (data_assets).'


def data_assets_check_status(value: Any) -> list[str]:
    """Field policy for Status inside Data Catalog."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Status is required on Data Catalog.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Status is zero; confirm the Data Catalog case.')
        if number > 9_000_000_000:
            notes.append('Status exceeds the Data Catalog ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Status must be YYYY-MM-DD for Data Catalog.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Status is longer than the Data Catalog ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Status placeholder values are not allowed on Data Catalog.')
    return notes


def data_assets_normalize_status(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def data_assets_describe_status() -> str:
    required = 'required' if True else 'optional'
    return 'Status is a ' + required + ' str field on Data Catalog (data_assets).'


FIELD_CHECKS_DATA_ASSETS = {
    'asset_key': data_assets_check_asset_key,
    'system_name': data_assets_check_system_name,
    'classification': data_assets_check_classification,
    'steward': data_assets_check_steward,
    'status': data_assets_check_status,
}


def data_assets_run_field_checks(row: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for name, checker in FIELD_CHECKS_DATA_ASSETS.items():
        found.extend(checker(row.get(name)))
    return found


def data_assets_policy_card(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'domain': DOMAIN_KEY,
        'title': DOMAIN_TITLE,
        'band': data_assets_risk_band(row),
        'owner': data_assets_owner_hint(row),
        'sla_hours': data_assets_sla_hours(row),
        'exceptions': data_assets_exception_needed(row),
        'freeze': data_assets_freeze_window(row),
        'violations': policy.collect(row) + data_assets_run_field_checks(row),
        'summary': data_assets_summary_line(row),
    }

