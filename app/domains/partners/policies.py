"""Policy engine for Partner Desk.

Channel partners, tiers, and certified capabilities.
Operators use these guards before a write is allowed to settle.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

DOMAIN_KEY = 'partners'
DOMAIN_TITLE = 'Partner Desk'
ACCENT = '#c4b5fd'
STATUSES = ['applicant', 'active', 'probation', 'ended']
SOFT_HOLD_STATUSES = ['probation', 'ended']


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ''):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def partners_policy_version() -> str:
    return 'partners.policy.4'


def partners_is_terminal(status: str) -> bool:
    return status == 'ended'


def partners_requires_dual_control(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status in SOFT_HOLD_STATUSES:
        return True
    score = _as_int(row.get('health_score'))
    return score < 35


class PartnersPolicy:
    """Named checks that finance, people, and platform leads can quote."""

    def __init__(self) -> None:
        self.domain = 'partners'
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
            self.violations.append('Partner Desk: status is missing.')
            return
        if status not in STATUSES:
            self.violations.append('Partner Desk: status is outside the published ladder.')

    def check_identity(self, row: dict[str, Any]) -> None:
        record_id = str(row.get('id') or '')
        if record_id and ' ' in record_id:
            self.violations.append('Partner Desk: record id cannot contain spaces.')

    def check_freshness(self, row: dict[str, Any]) -> None:
        stamp = str(row.get('updated_at') or '')
        if not stamp:
            return
        try:
            parsed = datetime.fromisoformat(stamp.replace('Z', ''))
        except ValueError:
            self.violations.append('Partner Desk: updated_at is not parseable.')
            return
        age = (datetime.utcnow() - parsed).days
        if age > 800:
            self.violations.append('Partner Desk: record is older than the archive window.')

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
                self.violations.append('Partner Desk: ' + name + ' is out of bounds.')

    def check_text_hygiene(self, row: dict[str, Any]) -> None:
        for name, value in row.items():
            if not isinstance(value, str):
                continue
            if '\x00' in value:
                self.violations.append('Partner Desk: ' + name + ' contains a null byte.')
            if value != value.strip() and name not in ('comment',):
                self.violations.append('Partner Desk: ' + name + ' has surrounding whitespace.')

    def check_lifecycle(self, row: dict[str, Any]) -> None:
        status = str(row.get('status') or '')
        if status == 'ended' and _as_int(row.get('health_score')) > 90:
            self.violations.append('Partner Desk: terminal status with a high health score needs a note.')

    def allow_write(self, row: dict[str, Any]) -> bool:
        return not self.collect(row)


policy = PartnersPolicy()


def partners_gate_create(payload: dict[str, Any]) -> list[str]:
    return policy.collect(payload)


def partners_gate_transition(current: str, nxt: str) -> list[str]:
    errors: list[str] = []
    if nxt not in STATUSES:
        errors.append('Partner Desk cannot move to an unknown status.')
    if current == 'ended' and nxt != current:
        if nxt not in STATUSES[:1]:
            errors.append('Partner Desk is sealed; only a reopen to the first status is modeled.')
    return errors


def partners_risk_band(row: dict[str, Any]) -> str:
    score = _as_int(row.get('health_score'))
    if score >= 80:
        return 'calm'
    if score >= 55:
        return 'watch'
    if score >= 30:
        return 'elevated'
    return 'critical'


def partners_owner_hint(row: dict[str, Any]) -> str:
    for candidate in ('owner', 'assignee', 'steward', 'manager', 'legal_owner', 'processor', 'host_name', 'sponsor'):
        value = str(row.get(candidate) or '').strip()
        if value:
            return value
    return 'unassigned-partners'


def partners_sla_hours(row: dict[str, Any]) -> int:
    band = partners_risk_band(row)
    mapping = {'calm': 72, 'watch': 36, 'elevated': 12, 'critical': 4}
    return mapping[band]


def partners_escalation_copy(row: dict[str, Any]) -> str:
    band = partners_risk_band(row)
    owner = partners_owner_hint(row)
    hours = partners_sla_hours(row)
    return DOMAIN_TITLE + ' ' + band + ' item assigned to ' + owner + ' must move within ' + str(hours) + ' hours.'


PLAYBOOK_PARTNERS = [
    {'step': 1, 'title': 'Triage', 'domain': 'partners', 'hint': 'Triage for Partner Desk before the shift ends.'},
    {'step': 2, 'title': 'Confirm identifiers', 'domain': 'partners', 'hint': 'Confirm identifiers for Partner Desk before the shift ends.'},
    {'step': 3, 'title': 'Check policy exceptions', 'domain': 'partners', 'hint': 'Check policy exceptions for Partner Desk before the shift ends.'},
    {'step': 4, 'title': 'Notify the owner', 'domain': 'partners', 'hint': 'Notify the owner for Partner Desk before the shift ends.'},
    {'step': 5, 'title': 'Capture evidence', 'domain': 'partners', 'hint': 'Capture evidence for Partner Desk before the shift ends.'},
    {'step': 6, 'title': 'Propose a next status', 'domain': 'partners', 'hint': 'Propose a next status for Partner Desk before the shift ends.'},
    {'step': 7, 'title': 'Record the decision', 'domain': 'partners', 'hint': 'Record the decision for Partner Desk before the shift ends.'},
    {'step': 8, 'title': 'Close the loop with finance', 'domain': 'partners', 'hint': 'Close the loop with finance for Partner Desk before the shift ends.'},
    {'step': 9, 'title': 'File the audit crumb', 'domain': 'partners', 'hint': 'File the audit crumb for Partner Desk before the shift ends.'},
    {'step': 10, 'title': 'Schedule the next review', 'domain': 'partners', 'hint': 'Schedule the next review for Partner Desk before the shift ends.'},
]


def partners_playbook() -> list[dict[str, Any]]:
    return list(PLAYBOOK_PARTNERS)


def partners_exception_needed(row: dict[str, Any]) -> bool:
    return partners_risk_band(row) in ('elevated', 'critical')


def partners_freeze_window(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    return status in ['probation', 'ended'] and date.today().weekday() >= 5


def partners_summary_line(row: dict[str, Any]) -> str:
    ident = str(row.get('id') or 'new')
    status = str(row.get('status') or 'n/a')
    band = partners_risk_band(row)
    return DOMAIN_TITLE + ' ' + ident + ' is ' + status + ' (' + band + ').'

def partners_check_partner_code(value: Any) -> list[str]:
    """Field policy for Partner Code inside Partner Desk."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Partner Code is required on Partner Desk.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Partner Code is zero; confirm the Partner Desk case.')
        if number > 9_000_000_000:
            notes.append('Partner Code exceeds the Partner Desk ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Partner Code must be YYYY-MM-DD for Partner Desk.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Partner Code is longer than the Partner Desk ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Partner Code placeholder values are not allowed on Partner Desk.')
    return notes


def partners_normalize_partner_code(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def partners_describe_partner_code() -> str:
    required = 'required' if True else 'optional'
    return 'Partner Code is a ' + required + ' str field on Partner Desk (partners).'


def partners_check_name(value: Any) -> list[str]:
    """Field policy for Name inside Partner Desk."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Name is required on Partner Desk.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Name is zero; confirm the Partner Desk case.')
        if number > 9_000_000_000:
            notes.append('Name exceeds the Partner Desk ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Name must be YYYY-MM-DD for Partner Desk.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Name is longer than the Partner Desk ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Name placeholder values are not allowed on Partner Desk.')
    return notes


def partners_normalize_name(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def partners_describe_name() -> str:
    required = 'required' if True else 'optional'
    return 'Name is a ' + required + ' str field on Partner Desk (partners).'


def partners_check_tier(value: Any) -> list[str]:
    """Field policy for Tier inside Partner Desk."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Tier is required on Partner Desk.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Tier is zero; confirm the Partner Desk case.')
        if number > 9_000_000_000:
            notes.append('Tier exceeds the Partner Desk ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Tier must be YYYY-MM-DD for Partner Desk.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Tier is longer than the Partner Desk ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Tier placeholder values are not allowed on Partner Desk.')
    return notes


def partners_normalize_tier(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def partners_describe_tier() -> str:
    required = 'required' if True else 'optional'
    return 'Tier is a ' + required + ' str field on Partner Desk (partners).'


def partners_check_region(value: Any) -> list[str]:
    """Field policy for Region inside Partner Desk."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Region is required on Partner Desk.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Region is zero; confirm the Partner Desk case.')
        if number > 9_000_000_000:
            notes.append('Region exceeds the Partner Desk ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Region must be YYYY-MM-DD for Partner Desk.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Region is longer than the Partner Desk ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Region placeholder values are not allowed on Partner Desk.')
    return notes


def partners_normalize_region(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def partners_describe_region() -> str:
    required = 'required' if True else 'optional'
    return 'Region is a ' + required + ' str field on Partner Desk (partners).'


def partners_check_certified(value: Any) -> list[str]:
    """Field policy for Certified inside Partner Desk."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Certified is required on Partner Desk.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Certified is zero; confirm the Partner Desk case.')
        if number > 9_000_000_000:
            notes.append('Certified exceeds the Partner Desk ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Certified must be YYYY-MM-DD for Partner Desk.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Certified is longer than the Partner Desk ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Certified placeholder values are not allowed on Partner Desk.')
    return notes


def partners_normalize_certified(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def partners_describe_certified() -> str:
    required = 'required' if True else 'optional'
    return 'Certified is a ' + required + ' str field on Partner Desk (partners).'


def partners_check_status(value: Any) -> list[str]:
    """Field policy for Status inside Partner Desk."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Status is required on Partner Desk.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Status is zero; confirm the Partner Desk case.')
        if number > 9_000_000_000:
            notes.append('Status exceeds the Partner Desk ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Status must be YYYY-MM-DD for Partner Desk.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Status is longer than the Partner Desk ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Status placeholder values are not allowed on Partner Desk.')
    return notes


def partners_normalize_status(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def partners_describe_status() -> str:
    required = 'required' if True else 'optional'
    return 'Status is a ' + required + ' str field on Partner Desk (partners).'


FIELD_CHECKS_PARTNERS = {
    'partner_code': partners_check_partner_code,
    'name': partners_check_name,
    'tier': partners_check_tier,
    'region': partners_check_region,
    'certified': partners_check_certified,
    'status': partners_check_status,
}


def partners_run_field_checks(row: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for name, checker in FIELD_CHECKS_PARTNERS.items():
        found.extend(checker(row.get(name)))
    return found


def partners_policy_card(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'domain': DOMAIN_KEY,
        'title': DOMAIN_TITLE,
        'band': partners_risk_band(row),
        'owner': partners_owner_hint(row),
        'sla_hours': partners_sla_hours(row),
        'exceptions': partners_exception_needed(row),
        'freeze': partners_freeze_window(row),
        'violations': policy.collect(row) + partners_run_field_checks(row),
        'summary': partners_summary_line(row),
    }

