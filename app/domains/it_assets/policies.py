"""Policy engine for IT Asset Register.

Laptops, phones, and peripherals with custodians and warranty clocks.
Operators use these guards before a write is allowed to settle.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

DOMAIN_KEY = 'it_assets'
DOMAIN_TITLE = 'IT Asset Register'
ACCENT = '#818cf8'
STATUSES = ['stock', 'assigned', 'repair', 'retired']
SOFT_HOLD_STATUSES = ['repair', 'retired']


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ''):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def it_assets_policy_version() -> str:
    return 'it_assets.policy.4'


def it_assets_is_terminal(status: str) -> bool:
    return status == 'retired'


def it_assets_requires_dual_control(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status in SOFT_HOLD_STATUSES:
        return True
    score = _as_int(row.get('health_score'))
    return score < 35


class ItAssetsPolicy:
    """Named checks that finance, people, and platform leads can quote."""

    def __init__(self) -> None:
        self.domain = 'it_assets'
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
            self.violations.append('IT Asset Register: status is missing.')
            return
        if status not in STATUSES:
            self.violations.append('IT Asset Register: status is outside the published ladder.')

    def check_identity(self, row: dict[str, Any]) -> None:
        record_id = str(row.get('id') or '')
        if record_id and ' ' in record_id:
            self.violations.append('IT Asset Register: record id cannot contain spaces.')

    def check_freshness(self, row: dict[str, Any]) -> None:
        stamp = str(row.get('updated_at') or '')
        if not stamp:
            return
        try:
            parsed = datetime.fromisoformat(stamp.replace('Z', ''))
        except ValueError:
            self.violations.append('IT Asset Register: updated_at is not parseable.')
            return
        age = (datetime.utcnow() - parsed).days
        if age > 800:
            self.violations.append('IT Asset Register: record is older than the archive window.')

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
                self.violations.append('IT Asset Register: ' + name + ' is out of bounds.')

    def check_text_hygiene(self, row: dict[str, Any]) -> None:
        for name, value in row.items():
            if not isinstance(value, str):
                continue
            if '\x00' in value:
                self.violations.append('IT Asset Register: ' + name + ' contains a null byte.')
            if value != value.strip() and name not in ('comment',):
                self.violations.append('IT Asset Register: ' + name + ' has surrounding whitespace.')

    def check_lifecycle(self, row: dict[str, Any]) -> None:
        status = str(row.get('status') or '')
        if status == 'retired' and _as_int(row.get('health_score')) > 90:
            self.violations.append('IT Asset Register: terminal status with a high health score needs a note.')

    def allow_write(self, row: dict[str, Any]) -> bool:
        return not self.collect(row)


policy = ItAssetsPolicy()


def it_assets_gate_create(payload: dict[str, Any]) -> list[str]:
    return policy.collect(payload)


def it_assets_gate_transition(current: str, nxt: str) -> list[str]:
    errors: list[str] = []
    if nxt not in STATUSES:
        errors.append('IT Asset Register cannot move to an unknown status.')
    if current == 'retired' and nxt != current:
        if nxt not in STATUSES[:1]:
            errors.append('IT Asset Register is sealed; only a reopen to the first status is modeled.')
    return errors


def it_assets_risk_band(row: dict[str, Any]) -> str:
    score = _as_int(row.get('health_score'))
    if score >= 80:
        return 'calm'
    if score >= 55:
        return 'watch'
    if score >= 30:
        return 'elevated'
    return 'critical'


def it_assets_owner_hint(row: dict[str, Any]) -> str:
    for candidate in ('owner', 'assignee', 'steward', 'manager', 'legal_owner', 'processor', 'host_name', 'sponsor'):
        value = str(row.get(candidate) or '').strip()
        if value:
            return value
    return 'unassigned-it_assets'


def it_assets_sla_hours(row: dict[str, Any]) -> int:
    band = it_assets_risk_band(row)
    mapping = {'calm': 72, 'watch': 36, 'elevated': 12, 'critical': 4}
    return mapping[band]


def it_assets_escalation_copy(row: dict[str, Any]) -> str:
    band = it_assets_risk_band(row)
    owner = it_assets_owner_hint(row)
    hours = it_assets_sla_hours(row)
    return DOMAIN_TITLE + ' ' + band + ' item assigned to ' + owner + ' must move within ' + str(hours) + ' hours.'


PLAYBOOK_IT_ASSETS = [
    {'step': 1, 'title': 'Triage', 'domain': 'it_assets', 'hint': 'Triage for IT Asset Register before the shift ends.'},
    {'step': 2, 'title': 'Confirm identifiers', 'domain': 'it_assets', 'hint': 'Confirm identifiers for IT Asset Register before the shift ends.'},
    {'step': 3, 'title': 'Check policy exceptions', 'domain': 'it_assets', 'hint': 'Check policy exceptions for IT Asset Register before the shift ends.'},
    {'step': 4, 'title': 'Notify the owner', 'domain': 'it_assets', 'hint': 'Notify the owner for IT Asset Register before the shift ends.'},
    {'step': 5, 'title': 'Capture evidence', 'domain': 'it_assets', 'hint': 'Capture evidence for IT Asset Register before the shift ends.'},
    {'step': 6, 'title': 'Propose a next status', 'domain': 'it_assets', 'hint': 'Propose a next status for IT Asset Register before the shift ends.'},
    {'step': 7, 'title': 'Record the decision', 'domain': 'it_assets', 'hint': 'Record the decision for IT Asset Register before the shift ends.'},
    {'step': 8, 'title': 'Close the loop with finance', 'domain': 'it_assets', 'hint': 'Close the loop with finance for IT Asset Register before the shift ends.'},
    {'step': 9, 'title': 'File the audit crumb', 'domain': 'it_assets', 'hint': 'File the audit crumb for IT Asset Register before the shift ends.'},
    {'step': 10, 'title': 'Schedule the next review', 'domain': 'it_assets', 'hint': 'Schedule the next review for IT Asset Register before the shift ends.'},
]


def it_assets_playbook() -> list[dict[str, Any]]:
    return list(PLAYBOOK_IT_ASSETS)


def it_assets_exception_needed(row: dict[str, Any]) -> bool:
    return it_assets_risk_band(row) in ('elevated', 'critical')


def it_assets_freeze_window(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    return status in ['repair', 'retired'] and date.today().weekday() >= 5


def it_assets_summary_line(row: dict[str, Any]) -> str:
    ident = str(row.get('id') or 'new')
    status = str(row.get('status') or 'n/a')
    band = it_assets_risk_band(row)
    return DOMAIN_TITLE + ' ' + ident + ' is ' + status + ' (' + band + ').'

def it_assets_check_asset_tag(value: Any) -> list[str]:
    """Field policy for Asset Tag inside IT Asset Register."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Asset Tag is required on IT Asset Register.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Asset Tag is zero; confirm the IT Asset Register case.')
        if number > 9_000_000_000:
            notes.append('Asset Tag exceeds the IT Asset Register ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Asset Tag must be YYYY-MM-DD for IT Asset Register.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Asset Tag is longer than the IT Asset Register ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Asset Tag placeholder values are not allowed on IT Asset Register.')
    return notes


def it_assets_normalize_asset_tag(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def it_assets_describe_asset_tag() -> str:
    required = 'required' if True else 'optional'
    return 'Asset Tag is a ' + required + ' str field on IT Asset Register (it_assets).'


def it_assets_check_model_name(value: Any) -> list[str]:
    """Field policy for Model Name inside IT Asset Register."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Model Name is required on IT Asset Register.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Model Name is zero; confirm the IT Asset Register case.')
        if number > 9_000_000_000:
            notes.append('Model Name exceeds the IT Asset Register ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Model Name must be YYYY-MM-DD for IT Asset Register.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Model Name is longer than the IT Asset Register ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Model Name placeholder values are not allowed on IT Asset Register.')
    return notes


def it_assets_normalize_model_name(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def it_assets_describe_model_name() -> str:
    required = 'required' if True else 'optional'
    return 'Model Name is a ' + required + ' str field on IT Asset Register (it_assets).'


def it_assets_check_custodian(value: Any) -> list[str]:
    """Field policy for Custodian inside IT Asset Register."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Custodian is required on IT Asset Register.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Custodian is zero; confirm the IT Asset Register case.')
        if number > 9_000_000_000:
            notes.append('Custodian exceeds the IT Asset Register ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Custodian must be YYYY-MM-DD for IT Asset Register.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Custodian is longer than the IT Asset Register ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Custodian placeholder values are not allowed on IT Asset Register.')
    return notes


def it_assets_normalize_custodian(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def it_assets_describe_custodian() -> str:
    required = 'required' if True else 'optional'
    return 'Custodian is a ' + required + ' str field on IT Asset Register (it_assets).'


def it_assets_check_warranty_on(value: Any) -> list[str]:
    """Field policy for Warranty On inside IT Asset Register."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Warranty On is required on IT Asset Register.')
        return notes
    if 'date' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Warranty On is zero; confirm the IT Asset Register case.')
        if number > 9_000_000_000:
            notes.append('Warranty On exceeds the IT Asset Register ceiling.')
        return notes
    if 'date' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Warranty On must be YYYY-MM-DD for IT Asset Register.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Warranty On is longer than the IT Asset Register ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Warranty On placeholder values are not allowed on IT Asset Register.')
    return notes


def it_assets_normalize_warranty_on(value: Any) -> Any:
    if 'date' == 'int':
        return _as_int(value)
    if 'date' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def it_assets_describe_warranty_on() -> str:
    required = 'required' if True else 'optional'
    return 'Warranty On is a ' + required + ' date field on IT Asset Register (it_assets).'


def it_assets_check_status(value: Any) -> list[str]:
    """Field policy for Status inside IT Asset Register."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Status is required on IT Asset Register.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Status is zero; confirm the IT Asset Register case.')
        if number > 9_000_000_000:
            notes.append('Status exceeds the IT Asset Register ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Status must be YYYY-MM-DD for IT Asset Register.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Status is longer than the IT Asset Register ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Status placeholder values are not allowed on IT Asset Register.')
    return notes


def it_assets_normalize_status(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def it_assets_describe_status() -> str:
    required = 'required' if True else 'optional'
    return 'Status is a ' + required + ' str field on IT Asset Register (it_assets).'


FIELD_CHECKS_IT_ASSETS = {
    'asset_tag': it_assets_check_asset_tag,
    'model_name': it_assets_check_model_name,
    'custodian': it_assets_check_custodian,
    'warranty_on': it_assets_check_warranty_on,
    'status': it_assets_check_status,
}


def it_assets_run_field_checks(row: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for name, checker in FIELD_CHECKS_IT_ASSETS.items():
        found.extend(checker(row.get(name)))
    return found


def it_assets_policy_card(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'domain': DOMAIN_KEY,
        'title': DOMAIN_TITLE,
        'band': it_assets_risk_band(row),
        'owner': it_assets_owner_hint(row),
        'sla_hours': it_assets_sla_hours(row),
        'exceptions': it_assets_exception_needed(row),
        'freeze': it_assets_freeze_window(row),
        'violations': policy.collect(row) + it_assets_run_field_checks(row),
        'summary': it_assets_summary_line(row),
    }

