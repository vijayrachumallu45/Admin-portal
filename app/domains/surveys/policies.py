"""Policy engine for Pulse Surveys.

Employee and customer pulse programs with response rates.
Operators use these guards before a write is allowed to settle.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

DOMAIN_KEY = 'surveys'
DOMAIN_TITLE = 'Pulse Surveys'
ACCENT = '#7dd3fc'
STATUSES = ['draft', 'open', 'closed', 'reported']
SOFT_HOLD_STATUSES = ['closed', 'reported']


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ''):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def surveys_policy_version() -> str:
    return 'surveys.policy.4'


def surveys_is_terminal(status: str) -> bool:
    return status == 'reported'


def surveys_requires_dual_control(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status in SOFT_HOLD_STATUSES:
        return True
    score = _as_int(row.get('health_score'))
    return score < 35


class SurveysPolicy:
    """Named checks that finance, people, and platform leads can quote."""

    def __init__(self) -> None:
        self.domain = 'surveys'
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
            self.violations.append('Pulse Surveys: status is missing.')
            return
        if status not in STATUSES:
            self.violations.append('Pulse Surveys: status is outside the published ladder.')

    def check_identity(self, row: dict[str, Any]) -> None:
        record_id = str(row.get('id') or '')
        if record_id and ' ' in record_id:
            self.violations.append('Pulse Surveys: record id cannot contain spaces.')

    def check_freshness(self, row: dict[str, Any]) -> None:
        stamp = str(row.get('updated_at') or '')
        if not stamp:
            return
        try:
            parsed = datetime.fromisoformat(stamp.replace('Z', ''))
        except ValueError:
            self.violations.append('Pulse Surveys: updated_at is not parseable.')
            return
        age = (datetime.utcnow() - parsed).days
        if age > 800:
            self.violations.append('Pulse Surveys: record is older than the archive window.')

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
                self.violations.append('Pulse Surveys: ' + name + ' is out of bounds.')

    def check_text_hygiene(self, row: dict[str, Any]) -> None:
        for name, value in row.items():
            if not isinstance(value, str):
                continue
            if '\x00' in value:
                self.violations.append('Pulse Surveys: ' + name + ' contains a null byte.')
            if value != value.strip() and name not in ('comment',):
                self.violations.append('Pulse Surveys: ' + name + ' has surrounding whitespace.')

    def check_lifecycle(self, row: dict[str, Any]) -> None:
        status = str(row.get('status') or '')
        if status == 'reported' and _as_int(row.get('health_score')) > 90:
            self.violations.append('Pulse Surveys: terminal status with a high health score needs a note.')

    def allow_write(self, row: dict[str, Any]) -> bool:
        return not self.collect(row)


policy = SurveysPolicy()


def surveys_gate_create(payload: dict[str, Any]) -> list[str]:
    return policy.collect(payload)


def surveys_gate_transition(current: str, nxt: str) -> list[str]:
    errors: list[str] = []
    if nxt not in STATUSES:
        errors.append('Pulse Surveys cannot move to an unknown status.')
    if current == 'reported' and nxt != current:
        if nxt not in STATUSES[:1]:
            errors.append('Pulse Surveys is sealed; only a reopen to the first status is modeled.')
    return errors


def surveys_risk_band(row: dict[str, Any]) -> str:
    score = _as_int(row.get('health_score'))
    if score >= 80:
        return 'calm'
    if score >= 55:
        return 'watch'
    if score >= 30:
        return 'elevated'
    return 'critical'


def surveys_owner_hint(row: dict[str, Any]) -> str:
    for candidate in ('owner', 'assignee', 'steward', 'manager', 'legal_owner', 'processor', 'host_name', 'sponsor'):
        value = str(row.get(candidate) or '').strip()
        if value:
            return value
    return 'unassigned-surveys'


def surveys_sla_hours(row: dict[str, Any]) -> int:
    band = surveys_risk_band(row)
    mapping = {'calm': 72, 'watch': 36, 'elevated': 12, 'critical': 4}
    return mapping[band]


def surveys_escalation_copy(row: dict[str, Any]) -> str:
    band = surveys_risk_band(row)
    owner = surveys_owner_hint(row)
    hours = surveys_sla_hours(row)
    return DOMAIN_TITLE + ' ' + band + ' item assigned to ' + owner + ' must move within ' + str(hours) + ' hours.'


PLAYBOOK_SURVEYS = [
    {'step': 1, 'title': 'Triage', 'domain': 'surveys', 'hint': 'Triage for Pulse Surveys before the shift ends.'},
    {'step': 2, 'title': 'Confirm identifiers', 'domain': 'surveys', 'hint': 'Confirm identifiers for Pulse Surveys before the shift ends.'},
    {'step': 3, 'title': 'Check policy exceptions', 'domain': 'surveys', 'hint': 'Check policy exceptions for Pulse Surveys before the shift ends.'},
    {'step': 4, 'title': 'Notify the owner', 'domain': 'surveys', 'hint': 'Notify the owner for Pulse Surveys before the shift ends.'},
    {'step': 5, 'title': 'Capture evidence', 'domain': 'surveys', 'hint': 'Capture evidence for Pulse Surveys before the shift ends.'},
    {'step': 6, 'title': 'Propose a next status', 'domain': 'surveys', 'hint': 'Propose a next status for Pulse Surveys before the shift ends.'},
    {'step': 7, 'title': 'Record the decision', 'domain': 'surveys', 'hint': 'Record the decision for Pulse Surveys before the shift ends.'},
    {'step': 8, 'title': 'Close the loop with finance', 'domain': 'surveys', 'hint': 'Close the loop with finance for Pulse Surveys before the shift ends.'},
    {'step': 9, 'title': 'File the audit crumb', 'domain': 'surveys', 'hint': 'File the audit crumb for Pulse Surveys before the shift ends.'},
    {'step': 10, 'title': 'Schedule the next review', 'domain': 'surveys', 'hint': 'Schedule the next review for Pulse Surveys before the shift ends.'},
]


def surveys_playbook() -> list[dict[str, Any]]:
    return list(PLAYBOOK_SURVEYS)


def surveys_exception_needed(row: dict[str, Any]) -> bool:
    return surveys_risk_band(row) in ('elevated', 'critical')


def surveys_freeze_window(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    return status in ['closed', 'reported'] and date.today().weekday() >= 5


def surveys_summary_line(row: dict[str, Any]) -> str:
    ident = str(row.get('id') or 'new')
    status = str(row.get('status') or 'n/a')
    band = surveys_risk_band(row)
    return DOMAIN_TITLE + ' ' + ident + ' is ' + status + ' (' + band + ').'

def surveys_check_survey_code(value: Any) -> list[str]:
    """Field policy for Survey Code inside Pulse Surveys."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Survey Code is required on Pulse Surveys.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Survey Code is zero; confirm the Pulse Surveys case.')
        if number > 9_000_000_000:
            notes.append('Survey Code exceeds the Pulse Surveys ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Survey Code must be YYYY-MM-DD for Pulse Surveys.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Survey Code is longer than the Pulse Surveys ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Survey Code placeholder values are not allowed on Pulse Surveys.')
    return notes


def surveys_normalize_survey_code(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def surveys_describe_survey_code() -> str:
    required = 'required' if True else 'optional'
    return 'Survey Code is a ' + required + ' str field on Pulse Surveys (surveys).'


def surveys_check_audience(value: Any) -> list[str]:
    """Field policy for Audience inside Pulse Surveys."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Audience is required on Pulse Surveys.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Audience is zero; confirm the Pulse Surveys case.')
        if number > 9_000_000_000:
            notes.append('Audience exceeds the Pulse Surveys ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Audience must be YYYY-MM-DD for Pulse Surveys.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Audience is longer than the Pulse Surveys ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Audience placeholder values are not allowed on Pulse Surveys.')
    return notes


def surveys_normalize_audience(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def surveys_describe_audience() -> str:
    required = 'required' if True else 'optional'
    return 'Audience is a ' + required + ' str field on Pulse Surveys (surveys).'


def surveys_check_opens_on(value: Any) -> list[str]:
    """Field policy for Opens On inside Pulse Surveys."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Opens On is required on Pulse Surveys.')
        return notes
    if 'date' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Opens On is zero; confirm the Pulse Surveys case.')
        if number > 9_000_000_000:
            notes.append('Opens On exceeds the Pulse Surveys ceiling.')
        return notes
    if 'date' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Opens On must be YYYY-MM-DD for Pulse Surveys.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Opens On is longer than the Pulse Surveys ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Opens On placeholder values are not allowed on Pulse Surveys.')
    return notes


def surveys_normalize_opens_on(value: Any) -> Any:
    if 'date' == 'int':
        return _as_int(value)
    if 'date' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def surveys_describe_opens_on() -> str:
    required = 'required' if True else 'optional'
    return 'Opens On is a ' + required + ' date field on Pulse Surveys (surveys).'


def surveys_check_closes_on(value: Any) -> list[str]:
    """Field policy for Closes On inside Pulse Surveys."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Closes On is required on Pulse Surveys.')
        return notes
    if 'date' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Closes On is zero; confirm the Pulse Surveys case.')
        if number > 9_000_000_000:
            notes.append('Closes On exceeds the Pulse Surveys ceiling.')
        return notes
    if 'date' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Closes On must be YYYY-MM-DD for Pulse Surveys.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Closes On is longer than the Pulse Surveys ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Closes On placeholder values are not allowed on Pulse Surveys.')
    return notes


def surveys_normalize_closes_on(value: Any) -> Any:
    if 'date' == 'int':
        return _as_int(value)
    if 'date' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def surveys_describe_closes_on() -> str:
    required = 'required' if True else 'optional'
    return 'Closes On is a ' + required + ' date field on Pulse Surveys (surveys).'


def surveys_check_target_n(value: Any) -> list[str]:
    """Field policy for Target N inside Pulse Surveys."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Target N is required on Pulse Surveys.')
        return notes
    if 'int' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Target N is zero; confirm the Pulse Surveys case.')
        if number > 9_000_000_000:
            notes.append('Target N exceeds the Pulse Surveys ceiling.')
        return notes
    if 'int' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Target N must be YYYY-MM-DD for Pulse Surveys.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Target N is longer than the Pulse Surveys ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Target N placeholder values are not allowed on Pulse Surveys.')
    return notes


def surveys_normalize_target_n(value: Any) -> Any:
    if 'int' == 'int':
        return _as_int(value)
    if 'int' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def surveys_describe_target_n() -> str:
    required = 'required' if True else 'optional'
    return 'Target N is a ' + required + ' int field on Pulse Surveys (surveys).'


def surveys_check_status(value: Any) -> list[str]:
    """Field policy for Status inside Pulse Surveys."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Status is required on Pulse Surveys.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Status is zero; confirm the Pulse Surveys case.')
        if number > 9_000_000_000:
            notes.append('Status exceeds the Pulse Surveys ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Status must be YYYY-MM-DD for Pulse Surveys.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Status is longer than the Pulse Surveys ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Status placeholder values are not allowed on Pulse Surveys.')
    return notes


def surveys_normalize_status(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def surveys_describe_status() -> str:
    required = 'required' if True else 'optional'
    return 'Status is a ' + required + ' str field on Pulse Surveys (surveys).'


FIELD_CHECKS_SURVEYS = {
    'survey_code': surveys_check_survey_code,
    'audience': surveys_check_audience,
    'opens_on': surveys_check_opens_on,
    'closes_on': surveys_check_closes_on,
    'target_n': surveys_check_target_n,
    'status': surveys_check_status,
}


def surveys_run_field_checks(row: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for name, checker in FIELD_CHECKS_SURVEYS.items():
        found.extend(checker(row.get(name)))
    return found


def surveys_policy_card(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'domain': DOMAIN_KEY,
        'title': DOMAIN_TITLE,
        'band': surveys_risk_band(row),
        'owner': surveys_owner_hint(row),
        'sla_hours': surveys_sla_hours(row),
        'exceptions': surveys_exception_needed(row),
        'freeze': surveys_freeze_window(row),
        'violations': policy.collect(row) + surveys_run_field_checks(row),
        'summary': surveys_summary_line(row),
    }

