"""Policy engine for Software Licenses.

Seat counts and renewal windows for commercial packages.
Operators use these guards before a write is allowed to settle.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

DOMAIN_KEY = 'software_licenses'
DOMAIN_TITLE = 'Software Licenses'
ACCENT = '#c084fc'
STATUSES = ['active', 'unused', 'expiring', 'expired']
SOFT_HOLD_STATUSES = ['expiring', 'expired']


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ''):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def software_licenses_policy_version() -> str:
    return 'software_licenses.policy.4'


def software_licenses_is_terminal(status: str) -> bool:
    return status == 'expired'


def software_licenses_requires_dual_control(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status in SOFT_HOLD_STATUSES:
        return True
    score = _as_int(row.get('health_score'))
    return score < 35


class SoftwareLicensesPolicy:
    """Named checks that finance, people, and platform leads can quote."""

    def __init__(self) -> None:
        self.domain = 'software_licenses'
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
            self.violations.append('Software Licenses: status is missing.')
            return
        if status not in STATUSES:
            self.violations.append('Software Licenses: status is outside the published ladder.')

    def check_identity(self, row: dict[str, Any]) -> None:
        record_id = str(row.get('id') or '')
        if record_id and ' ' in record_id:
            self.violations.append('Software Licenses: record id cannot contain spaces.')

    def check_freshness(self, row: dict[str, Any]) -> None:
        stamp = str(row.get('updated_at') or '')
        if not stamp:
            return
        try:
            parsed = datetime.fromisoformat(stamp.replace('Z', ''))
        except ValueError:
            self.violations.append('Software Licenses: updated_at is not parseable.')
            return
        age = (datetime.utcnow() - parsed).days
        if age > 800:
            self.violations.append('Software Licenses: record is older than the archive window.')

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
                self.violations.append('Software Licenses: ' + name + ' is out of bounds.')

    def check_text_hygiene(self, row: dict[str, Any]) -> None:
        for name, value in row.items():
            if not isinstance(value, str):
                continue
            if '\x00' in value:
                self.violations.append('Software Licenses: ' + name + ' contains a null byte.')
            if value != value.strip() and name not in ('comment',):
                self.violations.append('Software Licenses: ' + name + ' has surrounding whitespace.')

    def check_lifecycle(self, row: dict[str, Any]) -> None:
        status = str(row.get('status') or '')
        if status == 'expired' and _as_int(row.get('health_score')) > 90:
            self.violations.append('Software Licenses: terminal status with a high health score needs a note.')

    def allow_write(self, row: dict[str, Any]) -> bool:
        return not self.collect(row)


policy = SoftwareLicensesPolicy()


def software_licenses_gate_create(payload: dict[str, Any]) -> list[str]:
    return policy.collect(payload)


def software_licenses_gate_transition(current: str, nxt: str) -> list[str]:
    errors: list[str] = []
    if nxt not in STATUSES:
        errors.append('Software Licenses cannot move to an unknown status.')
    if current == 'expired' and nxt != current:
        if nxt not in STATUSES[:1]:
            errors.append('Software Licenses is sealed; only a reopen to the first status is modeled.')
    return errors


def software_licenses_risk_band(row: dict[str, Any]) -> str:
    score = _as_int(row.get('health_score'))
    if score >= 80:
        return 'calm'
    if score >= 55:
        return 'watch'
    if score >= 30:
        return 'elevated'
    return 'critical'


def software_licenses_owner_hint(row: dict[str, Any]) -> str:
    for candidate in ('owner', 'assignee', 'steward', 'manager', 'legal_owner', 'processor', 'host_name', 'sponsor'):
        value = str(row.get(candidate) or '').strip()
        if value:
            return value
    return 'unassigned-software_licenses'


def software_licenses_sla_hours(row: dict[str, Any]) -> int:
    band = software_licenses_risk_band(row)
    mapping = {'calm': 72, 'watch': 36, 'elevated': 12, 'critical': 4}
    return mapping[band]


def software_licenses_escalation_copy(row: dict[str, Any]) -> str:
    band = software_licenses_risk_band(row)
    owner = software_licenses_owner_hint(row)
    hours = software_licenses_sla_hours(row)
    return DOMAIN_TITLE + ' ' + band + ' item assigned to ' + owner + ' must move within ' + str(hours) + ' hours.'


PLAYBOOK_SOFTWARE_LICENSES = [
    {'step': 1, 'title': 'Triage', 'domain': 'software_licenses', 'hint': 'Triage for Software Licenses before the shift ends.'},
    {'step': 2, 'title': 'Confirm identifiers', 'domain': 'software_licenses', 'hint': 'Confirm identifiers for Software Licenses before the shift ends.'},
    {'step': 3, 'title': 'Check policy exceptions', 'domain': 'software_licenses', 'hint': 'Check policy exceptions for Software Licenses before the shift ends.'},
    {'step': 4, 'title': 'Notify the owner', 'domain': 'software_licenses', 'hint': 'Notify the owner for Software Licenses before the shift ends.'},
    {'step': 5, 'title': 'Capture evidence', 'domain': 'software_licenses', 'hint': 'Capture evidence for Software Licenses before the shift ends.'},
    {'step': 6, 'title': 'Propose a next status', 'domain': 'software_licenses', 'hint': 'Propose a next status for Software Licenses before the shift ends.'},
    {'step': 7, 'title': 'Record the decision', 'domain': 'software_licenses', 'hint': 'Record the decision for Software Licenses before the shift ends.'},
    {'step': 8, 'title': 'Close the loop with finance', 'domain': 'software_licenses', 'hint': 'Close the loop with finance for Software Licenses before the shift ends.'},
    {'step': 9, 'title': 'File the audit crumb', 'domain': 'software_licenses', 'hint': 'File the audit crumb for Software Licenses before the shift ends.'},
    {'step': 10, 'title': 'Schedule the next review', 'domain': 'software_licenses', 'hint': 'Schedule the next review for Software Licenses before the shift ends.'},
]


def software_licenses_playbook() -> list[dict[str, Any]]:
    return list(PLAYBOOK_SOFTWARE_LICENSES)


def software_licenses_exception_needed(row: dict[str, Any]) -> bool:
    return software_licenses_risk_band(row) in ('elevated', 'critical')


def software_licenses_freeze_window(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    return status in ['expiring', 'expired'] and date.today().weekday() >= 5


def software_licenses_summary_line(row: dict[str, Any]) -> str:
    ident = str(row.get('id') or 'new')
    status = str(row.get('status') or 'n/a')
    band = software_licenses_risk_band(row)
    return DOMAIN_TITLE + ' ' + ident + ' is ' + status + ' (' + band + ').'

def software_licenses_check_product_name(value: Any) -> list[str]:
    """Field policy for Product Name inside Software Licenses."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Product Name is required on Software Licenses.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Product Name is zero; confirm the Software Licenses case.')
        if number > 9_000_000_000:
            notes.append('Product Name exceeds the Software Licenses ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Product Name must be YYYY-MM-DD for Software Licenses.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Product Name is longer than the Software Licenses ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Product Name placeholder values are not allowed on Software Licenses.')
    return notes


def software_licenses_normalize_product_name(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def software_licenses_describe_product_name() -> str:
    required = 'required' if True else 'optional'
    return 'Product Name is a ' + required + ' str field on Software Licenses (software_licenses).'


def software_licenses_check_publisher(value: Any) -> list[str]:
    """Field policy for Publisher inside Software Licenses."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Publisher is required on Software Licenses.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Publisher is zero; confirm the Software Licenses case.')
        if number > 9_000_000_000:
            notes.append('Publisher exceeds the Software Licenses ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Publisher must be YYYY-MM-DD for Software Licenses.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Publisher is longer than the Software Licenses ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Publisher placeholder values are not allowed on Software Licenses.')
    return notes


def software_licenses_normalize_publisher(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def software_licenses_describe_publisher() -> str:
    required = 'required' if True else 'optional'
    return 'Publisher is a ' + required + ' str field on Software Licenses (software_licenses).'


def software_licenses_check_seats(value: Any) -> list[str]:
    """Field policy for Seats inside Software Licenses."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Seats is required on Software Licenses.')
        return notes
    if 'int' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Seats is zero; confirm the Software Licenses case.')
        if number > 9_000_000_000:
            notes.append('Seats exceeds the Software Licenses ceiling.')
        return notes
    if 'int' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Seats must be YYYY-MM-DD for Software Licenses.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Seats is longer than the Software Licenses ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Seats placeholder values are not allowed on Software Licenses.')
    return notes


def software_licenses_normalize_seats(value: Any) -> Any:
    if 'int' == 'int':
        return _as_int(value)
    if 'int' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def software_licenses_describe_seats() -> str:
    required = 'required' if True else 'optional'
    return 'Seats is a ' + required + ' int field on Software Licenses (software_licenses).'


def software_licenses_check_renew_on(value: Any) -> list[str]:
    """Field policy for Renew On inside Software Licenses."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Renew On is required on Software Licenses.')
        return notes
    if 'date' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Renew On is zero; confirm the Software Licenses case.')
        if number > 9_000_000_000:
            notes.append('Renew On exceeds the Software Licenses ceiling.')
        return notes
    if 'date' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Renew On must be YYYY-MM-DD for Software Licenses.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Renew On is longer than the Software Licenses ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Renew On placeholder values are not allowed on Software Licenses.')
    return notes


def software_licenses_normalize_renew_on(value: Any) -> Any:
    if 'date' == 'int':
        return _as_int(value)
    if 'date' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def software_licenses_describe_renew_on() -> str:
    required = 'required' if True else 'optional'
    return 'Renew On is a ' + required + ' date field on Software Licenses (software_licenses).'


def software_licenses_check_status(value: Any) -> list[str]:
    """Field policy for Status inside Software Licenses."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Status is required on Software Licenses.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Status is zero; confirm the Software Licenses case.')
        if number > 9_000_000_000:
            notes.append('Status exceeds the Software Licenses ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Status must be YYYY-MM-DD for Software Licenses.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Status is longer than the Software Licenses ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Status placeholder values are not allowed on Software Licenses.')
    return notes


def software_licenses_normalize_status(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def software_licenses_describe_status() -> str:
    required = 'required' if True else 'optional'
    return 'Status is a ' + required + ' str field on Software Licenses (software_licenses).'


FIELD_CHECKS_SOFTWARE_LICENSES = {
    'product_name': software_licenses_check_product_name,
    'publisher': software_licenses_check_publisher,
    'seats': software_licenses_check_seats,
    'renew_on': software_licenses_check_renew_on,
    'status': software_licenses_check_status,
}


def software_licenses_run_field_checks(row: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for name, checker in FIELD_CHECKS_SOFTWARE_LICENSES.items():
        found.extend(checker(row.get(name)))
    return found


def software_licenses_policy_card(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'domain': DOMAIN_KEY,
        'title': DOMAIN_TITLE,
        'band': software_licenses_risk_band(row),
        'owner': software_licenses_owner_hint(row),
        'sla_hours': software_licenses_sla_hours(row),
        'exceptions': software_licenses_exception_needed(row),
        'freeze': software_licenses_freeze_window(row),
        'violations': policy.collect(row) + software_licenses_run_field_checks(row),
        'summary': software_licenses_summary_line(row),
    }

