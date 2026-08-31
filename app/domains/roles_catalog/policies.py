"""Policy engine for Role Catalog.

Named permission bundles with risk ratings and approval owners.
Operators use these guards before a write is allowed to settle.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

DOMAIN_KEY = 'roles_catalog'
DOMAIN_TITLE = 'Role Catalog'
ACCENT = '#c9a227'
STATUSES = ['draft', 'published', 'deprecated']
SOFT_HOLD_STATUSES = ['published', 'deprecated']


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ''):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def roles_catalog_policy_version() -> str:
    return 'roles_catalog.policy.4'


def roles_catalog_is_terminal(status: str) -> bool:
    return status == 'deprecated'


def roles_catalog_requires_dual_control(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status in SOFT_HOLD_STATUSES:
        return True
    score = _as_int(row.get('health_score'))
    return score < 35


class RolesCatalogPolicy:
    """Named checks that finance, people, and platform leads can quote."""

    def __init__(self) -> None:
        self.domain = 'roles_catalog'
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
            self.violations.append('Role Catalog: status is missing.')
            return
        if status not in STATUSES:
            self.violations.append('Role Catalog: status is outside the published ladder.')

    def check_identity(self, row: dict[str, Any]) -> None:
        record_id = str(row.get('id') or '')
        if record_id and ' ' in record_id:
            self.violations.append('Role Catalog: record id cannot contain spaces.')

    def check_freshness(self, row: dict[str, Any]) -> None:
        stamp = str(row.get('updated_at') or '')
        if not stamp:
            return
        try:
            parsed = datetime.fromisoformat(stamp.replace('Z', ''))
        except ValueError:
            self.violations.append('Role Catalog: updated_at is not parseable.')
            return
        age = (datetime.utcnow() - parsed).days
        if age > 800:
            self.violations.append('Role Catalog: record is older than the archive window.')

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
                self.violations.append('Role Catalog: ' + name + ' is out of bounds.')

    def check_text_hygiene(self, row: dict[str, Any]) -> None:
        for name, value in row.items():
            if not isinstance(value, str):
                continue
            if '\x00' in value:
                self.violations.append('Role Catalog: ' + name + ' contains a null byte.')
            if value != value.strip() and name not in ('comment',):
                self.violations.append('Role Catalog: ' + name + ' has surrounding whitespace.')

    def check_lifecycle(self, row: dict[str, Any]) -> None:
        status = str(row.get('status') or '')
        if status == 'deprecated' and _as_int(row.get('health_score')) > 90:
            self.violations.append('Role Catalog: terminal status with a high health score needs a note.')

    def allow_write(self, row: dict[str, Any]) -> bool:
        return not self.collect(row)


policy = RolesCatalogPolicy()


def roles_catalog_gate_create(payload: dict[str, Any]) -> list[str]:
    return policy.collect(payload)


def roles_catalog_gate_transition(current: str, nxt: str) -> list[str]:
    errors: list[str] = []
    if nxt not in STATUSES:
        errors.append('Role Catalog cannot move to an unknown status.')
    if current == 'deprecated' and nxt != current:
        if nxt not in STATUSES[:1]:
            errors.append('Role Catalog is sealed; only a reopen to the first status is modeled.')
    return errors


def roles_catalog_risk_band(row: dict[str, Any]) -> str:
    score = _as_int(row.get('health_score'))
    if score >= 80:
        return 'calm'
    if score >= 55:
        return 'watch'
    if score >= 30:
        return 'elevated'
    return 'critical'


def roles_catalog_owner_hint(row: dict[str, Any]) -> str:
    for candidate in ('owner', 'assignee', 'steward', 'manager', 'legal_owner', 'processor', 'host_name', 'sponsor'):
        value = str(row.get(candidate) or '').strip()
        if value:
            return value
    return 'unassigned-roles_catalog'


def roles_catalog_sla_hours(row: dict[str, Any]) -> int:
    band = roles_catalog_risk_band(row)
    mapping = {'calm': 72, 'watch': 36, 'elevated': 12, 'critical': 4}
    return mapping[band]


def roles_catalog_escalation_copy(row: dict[str, Any]) -> str:
    band = roles_catalog_risk_band(row)
    owner = roles_catalog_owner_hint(row)
    hours = roles_catalog_sla_hours(row)
    return DOMAIN_TITLE + ' ' + band + ' item assigned to ' + owner + ' must move within ' + str(hours) + ' hours.'


PLAYBOOK_ROLES_CATALOG = [
    {'step': 1, 'title': 'Triage', 'domain': 'roles_catalog', 'hint': 'Triage for Role Catalog before the shift ends.'},
    {'step': 2, 'title': 'Confirm identifiers', 'domain': 'roles_catalog', 'hint': 'Confirm identifiers for Role Catalog before the shift ends.'},
    {'step': 3, 'title': 'Check policy exceptions', 'domain': 'roles_catalog', 'hint': 'Check policy exceptions for Role Catalog before the shift ends.'},
    {'step': 4, 'title': 'Notify the owner', 'domain': 'roles_catalog', 'hint': 'Notify the owner for Role Catalog before the shift ends.'},
    {'step': 5, 'title': 'Capture evidence', 'domain': 'roles_catalog', 'hint': 'Capture evidence for Role Catalog before the shift ends.'},
    {'step': 6, 'title': 'Propose a next status', 'domain': 'roles_catalog', 'hint': 'Propose a next status for Role Catalog before the shift ends.'},
    {'step': 7, 'title': 'Record the decision', 'domain': 'roles_catalog', 'hint': 'Record the decision for Role Catalog before the shift ends.'},
    {'step': 8, 'title': 'Close the loop with finance', 'domain': 'roles_catalog', 'hint': 'Close the loop with finance for Role Catalog before the shift ends.'},
    {'step': 9, 'title': 'File the audit crumb', 'domain': 'roles_catalog', 'hint': 'File the audit crumb for Role Catalog before the shift ends.'},
    {'step': 10, 'title': 'Schedule the next review', 'domain': 'roles_catalog', 'hint': 'Schedule the next review for Role Catalog before the shift ends.'},
]


def roles_catalog_playbook() -> list[dict[str, Any]]:
    return list(PLAYBOOK_ROLES_CATALOG)


def roles_catalog_exception_needed(row: dict[str, Any]) -> bool:
    return roles_catalog_risk_band(row) in ('elevated', 'critical')


def roles_catalog_freeze_window(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    return status in ['published', 'deprecated'] and date.today().weekday() >= 5


def roles_catalog_summary_line(row: dict[str, Any]) -> str:
    ident = str(row.get('id') or 'new')
    status = str(row.get('status') or 'n/a')
    band = roles_catalog_risk_band(row)
    return DOMAIN_TITLE + ' ' + ident + ' is ' + status + ' (' + band + ').'

def roles_catalog_check_role_key(value: Any) -> list[str]:
    """Field policy for Role Key inside Role Catalog."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Role Key is required on Role Catalog.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Role Key is zero; confirm the Role Catalog case.')
        if number > 9_000_000_000:
            notes.append('Role Key exceeds the Role Catalog ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Role Key must be YYYY-MM-DD for Role Catalog.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Role Key is longer than the Role Catalog ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Role Key placeholder values are not allowed on Role Catalog.')
    return notes


def roles_catalog_normalize_role_key(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def roles_catalog_describe_role_key() -> str:
    required = 'required' if True else 'optional'
    return 'Role Key is a ' + required + ' str field on Role Catalog (roles_catalog).'


def roles_catalog_check_display_name(value: Any) -> list[str]:
    """Field policy for Display Name inside Role Catalog."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Display Name is required on Role Catalog.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Display Name is zero; confirm the Role Catalog case.')
        if number > 9_000_000_000:
            notes.append('Display Name exceeds the Role Catalog ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Display Name must be YYYY-MM-DD for Role Catalog.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Display Name is longer than the Role Catalog ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Display Name placeholder values are not allowed on Role Catalog.')
    return notes


def roles_catalog_normalize_display_name(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def roles_catalog_describe_display_name() -> str:
    required = 'required' if True else 'optional'
    return 'Display Name is a ' + required + ' str field on Role Catalog (roles_catalog).'


def roles_catalog_check_risk_level(value: Any) -> list[str]:
    """Field policy for Risk Level inside Role Catalog."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Risk Level is required on Role Catalog.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Risk Level is zero; confirm the Role Catalog case.')
        if number > 9_000_000_000:
            notes.append('Risk Level exceeds the Role Catalog ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Risk Level must be YYYY-MM-DD for Role Catalog.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Risk Level is longer than the Role Catalog ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Risk Level placeholder values are not allowed on Role Catalog.')
    return notes


def roles_catalog_normalize_risk_level(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def roles_catalog_describe_risk_level() -> str:
    required = 'required' if True else 'optional'
    return 'Risk Level is a ' + required + ' str field on Role Catalog (roles_catalog).'


def roles_catalog_check_owner_team(value: Any) -> list[str]:
    """Field policy for Owner Team inside Role Catalog."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Owner Team is required on Role Catalog.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Owner Team is zero; confirm the Role Catalog case.')
        if number > 9_000_000_000:
            notes.append('Owner Team exceeds the Role Catalog ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Owner Team must be YYYY-MM-DD for Role Catalog.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Owner Team is longer than the Role Catalog ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Owner Team placeholder values are not allowed on Role Catalog.')
    return notes


def roles_catalog_normalize_owner_team(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def roles_catalog_describe_owner_team() -> str:
    required = 'required' if True else 'optional'
    return 'Owner Team is a ' + required + ' str field on Role Catalog (roles_catalog).'


def roles_catalog_check_max_holders(value: Any) -> list[str]:
    """Field policy for Max Holders inside Role Catalog."""
    notes: list[str] = []
    if value in (None, '') and False:
        notes.append('Max Holders is required on Role Catalog.')
        return notes
    if 'int' == 'int':
        number = _as_int(value, default=0)
        if False and number == 0:
            notes.append('Max Holders is zero; confirm the Role Catalog case.')
        if number > 9_000_000_000:
            notes.append('Max Holders exceeds the Role Catalog ceiling.')
        return notes
    if 'int' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Max Holders must be YYYY-MM-DD for Role Catalog.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Max Holders is longer than the Role Catalog ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and False:
        notes.append('Max Holders placeholder values are not allowed on Role Catalog.')
    return notes


def roles_catalog_normalize_max_holders(value: Any) -> Any:
    if 'int' == 'int':
        return _as_int(value)
    if 'int' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def roles_catalog_describe_max_holders() -> str:
    required = 'required' if False else 'optional'
    return 'Max Holders is a ' + required + ' int field on Role Catalog (roles_catalog).'


def roles_catalog_check_review_days(value: Any) -> list[str]:
    """Field policy for Review Days inside Role Catalog."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Review Days is required on Role Catalog.')
        return notes
    if 'int' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Review Days is zero; confirm the Role Catalog case.')
        if number > 9_000_000_000:
            notes.append('Review Days exceeds the Role Catalog ceiling.')
        return notes
    if 'int' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Review Days must be YYYY-MM-DD for Role Catalog.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Review Days is longer than the Role Catalog ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Review Days placeholder values are not allowed on Role Catalog.')
    return notes


def roles_catalog_normalize_review_days(value: Any) -> Any:
    if 'int' == 'int':
        return _as_int(value)
    if 'int' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def roles_catalog_describe_review_days() -> str:
    required = 'required' if True else 'optional'
    return 'Review Days is a ' + required + ' int field on Role Catalog (roles_catalog).'


def roles_catalog_check_status(value: Any) -> list[str]:
    """Field policy for Status inside Role Catalog."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Status is required on Role Catalog.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Status is zero; confirm the Role Catalog case.')
        if number > 9_000_000_000:
            notes.append('Status exceeds the Role Catalog ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Status must be YYYY-MM-DD for Role Catalog.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Status is longer than the Role Catalog ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Status placeholder values are not allowed on Role Catalog.')
    return notes


def roles_catalog_normalize_status(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def roles_catalog_describe_status() -> str:
    required = 'required' if True else 'optional'
    return 'Status is a ' + required + ' str field on Role Catalog (roles_catalog).'


FIELD_CHECKS_ROLES_CATALOG = {
    'role_key': roles_catalog_check_role_key,
    'display_name': roles_catalog_check_display_name,
    'risk_level': roles_catalog_check_risk_level,
    'owner_team': roles_catalog_check_owner_team,
    'max_holders': roles_catalog_check_max_holders,
    'review_days': roles_catalog_check_review_days,
    'status': roles_catalog_check_status,
}


def roles_catalog_run_field_checks(row: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for name, checker in FIELD_CHECKS_ROLES_CATALOG.items():
        found.extend(checker(row.get(name)))
    return found


def roles_catalog_policy_card(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'domain': DOMAIN_KEY,
        'title': DOMAIN_TITLE,
        'band': roles_catalog_risk_band(row),
        'owner': roles_catalog_owner_hint(row),
        'sla_hours': roles_catalog_sla_hours(row),
        'exceptions': roles_catalog_exception_needed(row),
        'freeze': roles_catalog_freeze_window(row),
        'violations': policy.collect(row) + roles_catalog_run_field_checks(row),
        'summary': roles_catalog_summary_line(row),
    }

