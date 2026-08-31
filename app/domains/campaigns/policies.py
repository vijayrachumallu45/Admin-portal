"""Policy engine for Campaign Studio.

Outbound programs with budget, channel mix, and lift tracking.
Operators use these guards before a write is allowed to settle.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

DOMAIN_KEY = 'campaigns'
DOMAIN_TITLE = 'Campaign Studio'
ACCENT = '#e879f9'
STATUSES = ['planned', 'live', 'paused', 'complete']
SOFT_HOLD_STATUSES = ['paused', 'complete']


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ''):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def campaigns_policy_version() -> str:
    return 'campaigns.policy.4'


def campaigns_is_terminal(status: str) -> bool:
    return status == 'complete'


def campaigns_requires_dual_control(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status in SOFT_HOLD_STATUSES:
        return True
    score = _as_int(row.get('health_score'))
    return score < 35


class CampaignsPolicy:
    """Named checks that finance, people, and platform leads can quote."""

    def __init__(self) -> None:
        self.domain = 'campaigns'
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
            self.violations.append('Campaign Studio: status is missing.')
            return
        if status not in STATUSES:
            self.violations.append('Campaign Studio: status is outside the published ladder.')

    def check_identity(self, row: dict[str, Any]) -> None:
        record_id = str(row.get('id') or '')
        if record_id and ' ' in record_id:
            self.violations.append('Campaign Studio: record id cannot contain spaces.')

    def check_freshness(self, row: dict[str, Any]) -> None:
        stamp = str(row.get('updated_at') or '')
        if not stamp:
            return
        try:
            parsed = datetime.fromisoformat(stamp.replace('Z', ''))
        except ValueError:
            self.violations.append('Campaign Studio: updated_at is not parseable.')
            return
        age = (datetime.utcnow() - parsed).days
        if age > 800:
            self.violations.append('Campaign Studio: record is older than the archive window.')

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
                self.violations.append('Campaign Studio: ' + name + ' is out of bounds.')

    def check_text_hygiene(self, row: dict[str, Any]) -> None:
        for name, value in row.items():
            if not isinstance(value, str):
                continue
            if '\x00' in value:
                self.violations.append('Campaign Studio: ' + name + ' contains a null byte.')
            if value != value.strip() and name not in ('comment',):
                self.violations.append('Campaign Studio: ' + name + ' has surrounding whitespace.')

    def check_lifecycle(self, row: dict[str, Any]) -> None:
        status = str(row.get('status') or '')
        if status == 'complete' and _as_int(row.get('health_score')) > 90:
            self.violations.append('Campaign Studio: terminal status with a high health score needs a note.')

    def allow_write(self, row: dict[str, Any]) -> bool:
        return not self.collect(row)


policy = CampaignsPolicy()


def campaigns_gate_create(payload: dict[str, Any]) -> list[str]:
    return policy.collect(payload)


def campaigns_gate_transition(current: str, nxt: str) -> list[str]:
    errors: list[str] = []
    if nxt not in STATUSES:
        errors.append('Campaign Studio cannot move to an unknown status.')
    if current == 'complete' and nxt != current:
        if nxt not in STATUSES[:1]:
            errors.append('Campaign Studio is sealed; only a reopen to the first status is modeled.')
    return errors


def campaigns_risk_band(row: dict[str, Any]) -> str:
    score = _as_int(row.get('health_score'))
    if score >= 80:
        return 'calm'
    if score >= 55:
        return 'watch'
    if score >= 30:
        return 'elevated'
    return 'critical'


def campaigns_owner_hint(row: dict[str, Any]) -> str:
    for candidate in ('owner', 'assignee', 'steward', 'manager', 'legal_owner', 'processor', 'host_name', 'sponsor'):
        value = str(row.get(candidate) or '').strip()
        if value:
            return value
    return 'unassigned-campaigns'


def campaigns_sla_hours(row: dict[str, Any]) -> int:
    band = campaigns_risk_band(row)
    mapping = {'calm': 72, 'watch': 36, 'elevated': 12, 'critical': 4}
    return mapping[band]


def campaigns_escalation_copy(row: dict[str, Any]) -> str:
    band = campaigns_risk_band(row)
    owner = campaigns_owner_hint(row)
    hours = campaigns_sla_hours(row)
    return DOMAIN_TITLE + ' ' + band + ' item assigned to ' + owner + ' must move within ' + str(hours) + ' hours.'


PLAYBOOK_CAMPAIGNS = [
    {'step': 1, 'title': 'Triage', 'domain': 'campaigns', 'hint': 'Triage for Campaign Studio before the shift ends.'},
    {'step': 2, 'title': 'Confirm identifiers', 'domain': 'campaigns', 'hint': 'Confirm identifiers for Campaign Studio before the shift ends.'},
    {'step': 3, 'title': 'Check policy exceptions', 'domain': 'campaigns', 'hint': 'Check policy exceptions for Campaign Studio before the shift ends.'},
    {'step': 4, 'title': 'Notify the owner', 'domain': 'campaigns', 'hint': 'Notify the owner for Campaign Studio before the shift ends.'},
    {'step': 5, 'title': 'Capture evidence', 'domain': 'campaigns', 'hint': 'Capture evidence for Campaign Studio before the shift ends.'},
    {'step': 6, 'title': 'Propose a next status', 'domain': 'campaigns', 'hint': 'Propose a next status for Campaign Studio before the shift ends.'},
    {'step': 7, 'title': 'Record the decision', 'domain': 'campaigns', 'hint': 'Record the decision for Campaign Studio before the shift ends.'},
    {'step': 8, 'title': 'Close the loop with finance', 'domain': 'campaigns', 'hint': 'Close the loop with finance for Campaign Studio before the shift ends.'},
    {'step': 9, 'title': 'File the audit crumb', 'domain': 'campaigns', 'hint': 'File the audit crumb for Campaign Studio before the shift ends.'},
    {'step': 10, 'title': 'Schedule the next review', 'domain': 'campaigns', 'hint': 'Schedule the next review for Campaign Studio before the shift ends.'},
]


def campaigns_playbook() -> list[dict[str, Any]]:
    return list(PLAYBOOK_CAMPAIGNS)


def campaigns_exception_needed(row: dict[str, Any]) -> bool:
    return campaigns_risk_band(row) in ('elevated', 'critical')


def campaigns_freeze_window(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    return status in ['paused', 'complete'] and date.today().weekday() >= 5


def campaigns_summary_line(row: dict[str, Any]) -> str:
    ident = str(row.get('id') or 'new')
    status = str(row.get('status') or 'n/a')
    band = campaigns_risk_band(row)
    return DOMAIN_TITLE + ' ' + ident + ' is ' + status + ' (' + band + ').'

def campaigns_check_campaign_name(value: Any) -> list[str]:
    """Field policy for Campaign Name inside Campaign Studio."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Campaign Name is required on Campaign Studio.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Campaign Name is zero; confirm the Campaign Studio case.')
        if number > 9_000_000_000:
            notes.append('Campaign Name exceeds the Campaign Studio ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Campaign Name must be YYYY-MM-DD for Campaign Studio.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Campaign Name is longer than the Campaign Studio ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Campaign Name placeholder values are not allowed on Campaign Studio.')
    return notes


def campaigns_normalize_campaign_name(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def campaigns_describe_campaign_name() -> str:
    required = 'required' if True else 'optional'
    return 'Campaign Name is a ' + required + ' str field on Campaign Studio (campaigns).'


def campaigns_check_channel(value: Any) -> list[str]:
    """Field policy for Channel inside Campaign Studio."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Channel is required on Campaign Studio.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Channel is zero; confirm the Campaign Studio case.')
        if number > 9_000_000_000:
            notes.append('Channel exceeds the Campaign Studio ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Channel must be YYYY-MM-DD for Campaign Studio.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Channel is longer than the Campaign Studio ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Channel placeholder values are not allowed on Campaign Studio.')
    return notes


def campaigns_normalize_channel(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def campaigns_describe_channel() -> str:
    required = 'required' if True else 'optional'
    return 'Channel is a ' + required + ' str field on Campaign Studio (campaigns).'


def campaigns_check_budget_cents(value: Any) -> list[str]:
    """Field policy for Budget Cents inside Campaign Studio."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Budget Cents is required on Campaign Studio.')
        return notes
    if 'int' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Budget Cents is zero; confirm the Campaign Studio case.')
        if number > 9_000_000_000:
            notes.append('Budget Cents exceeds the Campaign Studio ceiling.')
        return notes
    if 'int' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Budget Cents must be YYYY-MM-DD for Campaign Studio.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Budget Cents is longer than the Campaign Studio ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Budget Cents placeholder values are not allowed on Campaign Studio.')
    return notes


def campaigns_normalize_budget_cents(value: Any) -> Any:
    if 'int' == 'int':
        return _as_int(value)
    if 'int' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def campaigns_describe_budget_cents() -> str:
    required = 'required' if True else 'optional'
    return 'Budget Cents is a ' + required + ' int field on Campaign Studio (campaigns).'


def campaigns_check_starts_on(value: Any) -> list[str]:
    """Field policy for Starts On inside Campaign Studio."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Starts On is required on Campaign Studio.')
        return notes
    if 'date' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Starts On is zero; confirm the Campaign Studio case.')
        if number > 9_000_000_000:
            notes.append('Starts On exceeds the Campaign Studio ceiling.')
        return notes
    if 'date' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Starts On must be YYYY-MM-DD for Campaign Studio.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Starts On is longer than the Campaign Studio ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Starts On placeholder values are not allowed on Campaign Studio.')
    return notes


def campaigns_normalize_starts_on(value: Any) -> Any:
    if 'date' == 'int':
        return _as_int(value)
    if 'date' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def campaigns_describe_starts_on() -> str:
    required = 'required' if True else 'optional'
    return 'Starts On is a ' + required + ' date field on Campaign Studio (campaigns).'


def campaigns_check_ends_on(value: Any) -> list[str]:
    """Field policy for Ends On inside Campaign Studio."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Ends On is required on Campaign Studio.')
        return notes
    if 'date' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Ends On is zero; confirm the Campaign Studio case.')
        if number > 9_000_000_000:
            notes.append('Ends On exceeds the Campaign Studio ceiling.')
        return notes
    if 'date' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Ends On must be YYYY-MM-DD for Campaign Studio.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Ends On is longer than the Campaign Studio ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Ends On placeholder values are not allowed on Campaign Studio.')
    return notes


def campaigns_normalize_ends_on(value: Any) -> Any:
    if 'date' == 'int':
        return _as_int(value)
    if 'date' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def campaigns_describe_ends_on() -> str:
    required = 'required' if True else 'optional'
    return 'Ends On is a ' + required + ' date field on Campaign Studio (campaigns).'


def campaigns_check_status(value: Any) -> list[str]:
    """Field policy for Status inside Campaign Studio."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Status is required on Campaign Studio.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Status is zero; confirm the Campaign Studio case.')
        if number > 9_000_000_000:
            notes.append('Status exceeds the Campaign Studio ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Status must be YYYY-MM-DD for Campaign Studio.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Status is longer than the Campaign Studio ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Status placeholder values are not allowed on Campaign Studio.')
    return notes


def campaigns_normalize_status(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def campaigns_describe_status() -> str:
    required = 'required' if True else 'optional'
    return 'Status is a ' + required + ' str field on Campaign Studio (campaigns).'


FIELD_CHECKS_CAMPAIGNS = {
    'campaign_name': campaigns_check_campaign_name,
    'channel': campaigns_check_channel,
    'budget_cents': campaigns_check_budget_cents,
    'starts_on': campaigns_check_starts_on,
    'ends_on': campaigns_check_ends_on,
    'status': campaigns_check_status,
}


def campaigns_run_field_checks(row: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for name, checker in FIELD_CHECKS_CAMPAIGNS.items():
        found.extend(checker(row.get(name)))
    return found


def campaigns_policy_card(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'domain': DOMAIN_KEY,
        'title': DOMAIN_TITLE,
        'band': campaigns_risk_band(row),
        'owner': campaigns_owner_hint(row),
        'sla_hours': campaigns_sla_hours(row),
        'exceptions': campaigns_exception_needed(row),
        'freeze': campaigns_freeze_window(row),
        'violations': policy.collect(row) + campaigns_run_field_checks(row),
        'summary': campaigns_summary_line(row),
    }

