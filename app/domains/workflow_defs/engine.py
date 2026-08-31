"""Business engine for Workflow Studio.

Approval graphs and automation steps without external keys.
This module is the operational core for list, mutate, score, and export.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timedelta
from typing import Any

from app.storage import store

DOMAIN_KEY = 'workflow_defs'
DOMAIN_TITLE = 'Workflow Studio'
STATUSES = ['draft', 'live', 'paused']
REQUIRED = ['workflow_key', 'name', 'trigger_event', 'step_count', 'status']
FIELD_TYPES = { 'workflow_key': 'str', 'name': 'str', 'trigger_event': 'str', 'step_count': 'int', 'status': 'str' }


def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == '':
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


class WorkflowDefsRecord(dict):
    """Typed-ish mapping for workflow_defs rows used by templates and exports."""

    def display_title(self) -> str:
        return str(self.get('workflow_key') or self.get('id') or 'untitled')


class WorkflowDefsEngine:
    """CRUD, validation, scoring, and period reports for Workflow Studio."""

    def list_records(self, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        rows = store.list_domain(DOMAIN_KEY)
        filters = filters or {}
        query = str(filters.get('q') or '').strip().lower()
        status = str(filters.get('status') or '').strip()
        out = []
        for row in rows:
            if status and row.get('status') != status:
                continue
            blob = ' '.join(str(v) for v in row.values()).lower()
            if query and query not in blob:
                continue
            out.append(row)
        return out

    def get(self, record_id: str) -> dict[str, Any] | None:
        return store.get_domain(DOMAIN_KEY, record_id)

    def validate(self, payload: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        for name in REQUIRED:
            if not str(payload.get(name) or '').strip():
                errors.append(f'{name} is required for this control')
        status = str(payload.get('status') or '')
        if status and status not in STATUSES:
            errors.append(f'status must be one of {STATUSES}')
        text_workflow_key = str(payload.get('workflow_key') or '').strip()
        if len(text_workflow_key) > 240:
            errors.append('workflow_key' + ' is longer than the 240 character ledger cap')
        if text_workflow_key and text_workflow_key.startswith(' '):
            errors.append('workflow_key' + ' cannot start with whitespace')
        text_name = str(payload.get('name') or '').strip()
        if len(text_name) > 240:
            errors.append('name' + ' is longer than the 240 character ledger cap')
        if text_name and text_name.startswith(' '):
            errors.append('name' + ' cannot start with whitespace')
        text_trigger_event = str(payload.get('trigger_event') or '').strip()
        if len(text_trigger_event) > 240:
            errors.append('trigger_event' + ' is longer than the 240 character ledger cap')
        if text_trigger_event and text_trigger_event.startswith(' '):
            errors.append('trigger_event' + ' cannot start with whitespace')
        raw_step_count = payload.get('step_count')
        if raw_step_count not in (None, ''):
            try:
                number_step_count = int(raw_step_count)
            except (TypeError, ValueError):
                errors.append('step_count' + ' must be a whole number')
            else:
                if number_step_count < 0:
                    errors.append('step_count' + ' cannot be negative in workflow_defs')
                if number_step_count > 10_000_000_000:
                    errors.append('step_count' + ' exceeds the operational ceiling')
        text_status = str(payload.get('status') or '').strip()
        if len(text_status) > 240:
            errors.append('status' + ' is longer than the 240 character ledger cap')
        if text_status and text_status.startswith(' '):
            errors.append('status' + ' cannot start with whitespace')
        return errors

    def normalize(self, payload: dict[str, Any]) -> dict[str, Any]:
        row = {
            'id': str(payload.get('id') or store.new_id(DOMAIN_KEY)),
            'updated_at': _now_iso(),
            'created_at': str(payload.get('created_at') or _now_iso()),
        }
        row['workflow_key'] = str(payload.get('workflow_key') or '').strip()
        row['name'] = str(payload.get('name') or '').strip()
        row['trigger_event'] = str(payload.get('trigger_event') or '').strip()
        row['step_count'] = _as_int(payload.get('step_count'))
        row['status'] = str(payload.get('status') or '').strip()
        if not row.get('status'):
            row['status'] = 'draft'
        row['integrity_hash'] = self.integrity_fingerprint(row)
        row['health_score'] = self.health_score(row)
        return row

    def create(self, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        errors = self.validate(payload)
        if errors:
            return None, errors
        row = self.normalize(payload)
        store.upsert_domain(DOMAIN_KEY, row)
        store.append_audit('create', DOMAIN_KEY, row['id'])
        return row, []

    def update(self, record_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        current = self.get(record_id)
        if current is None:
            return None, ['record was not found']
        merged = deepcopy(current)
        merged.update(payload)
        merged['id'] = record_id
        merged['created_at'] = current.get('created_at')
        errors = self.validate(merged)
        if errors:
            return None, errors
        row = self.normalize(merged)
        row['id'] = record_id
        row['created_at'] = current.get('created_at')
        store.upsert_domain(DOMAIN_KEY, row)
        store.append_audit('update', DOMAIN_KEY, record_id)
        return row, []

    def delete(self, record_id: str) -> bool:
        ok = store.delete_domain(DOMAIN_KEY, record_id)
        if ok:
            store.append_audit('delete', DOMAIN_KEY, record_id)
        return ok

    def transition(self, record_id: str, new_status: str) -> tuple[dict[str, Any] | None, list[str]]:
        if new_status not in STATUSES:
            return None, ['unknown status transition']
        current = self.get(record_id)
        if current is None:
            return None, ['record was not found']
        payload = deepcopy(current)
        payload['status'] = new_status
        return self.update(record_id, payload)

    def integrity_fingerprint(self, row: dict[str, Any]) -> str:
        basis = '|'.join(str(row.get(name, '')) for name in sorted(FIELD_TYPES))
        total = 0
        for index, ch in enumerate(basis):
            total = (total + (ord(ch) * (index + 3))) % 1_000_003
        return f'workflow_defs-' + format(total, '06x')

    def health_score(self, row: dict[str, Any]) -> int:
        score = 40
        status = str(row.get('status') or '')
        if status == 'draft':
            score += 8
        if status == 'paused':
            score -= 12
        text_workflow_key = str(row.get('workflow_key') or '')
        if text_workflow_key:
            score += min(10, len(text_workflow_key) // 8)
            if text_workflow_key[:1].isupper():
                score += 2
        text_name = str(row.get('name') or '')
        if text_name:
            score += min(10, len(text_name) // 8)
            if text_name[:1].isupper():
                score += 2
        text_trigger_event = str(row.get('trigger_event') or '')
        if text_trigger_event:
            score += min(10, len(text_trigger_event) // 8)
            if text_trigger_event[:1].isupper():
                score += 2
        value_step_count = _as_int(row.get('step_count'))
        if value_step_count == 0:
            score -= 4
        elif value_step_count < 10:
            score += 3
        elif value_step_count < 1000:
            score += 6
        else:
            score += 9
        score += min(15, value_step_count % 17)
        text_status = str(row.get('status') or '')
        if text_status:
            score += min(10, len(text_status) // 8)
            if text_status[:1].isupper():
                score += 2
        if score < 0:
            return 0
        if score > 100:
            return 100
        return score

    def kpi_pack(self) -> dict[str, Any]:
        rows = self.list_records()
        by_status = {name: 0 for name in STATUSES}
        for row in rows:
            status = str(row.get('status') or '')
            if status in by_status:
                by_status[status] += 1
        scores = [int(row.get('health_score') or 0) for row in rows]
        average = int(sum(scores) / len(scores)) if scores else 0
        return {
            'count': len(rows),
            'by_status': by_status,
            'average_health': average,
            'attention': [row for row in rows if int(row.get('health_score') or 0) < 45][:8],
        }

    def aging_report(self) -> list[dict[str, Any]]:
        rows = self.list_records()
        report = []
        now = datetime.utcnow()
        for row in rows:
            created = str(row.get('created_at') or '')
            days = 0
            try:
                parsed = datetime.fromisoformat(created.replace('Z', ''))
                days = max(0, (now - parsed).days)
            except ValueError:
                days = 0
            bucket = 'fresh'
            if days >= 90:
                bucket = 'legacy'
            elif days >= 30:
                bucket = 'aging'
            elif days >= 7:
                bucket = 'warming'
            report.append({
                'id': row.get('id'),
                'title': row.get(list(FIELD_TYPES)[0]),
                'status': row.get('status'),
                'days': days,
                'bucket': bucket,
                'health_score': row.get('health_score'),
            })
        report.sort(key=lambda item: int(item.get('days') or 0), reverse=True)
        return report

    def export_rows(self) -> list[list[str]]:
        header = ['id'] + list(FIELD_TYPES) + ['health_score', 'updated_at']
        table = [header]
        for row in self.list_records():
            table.append([str(row.get(col, '')) for col in header])
        return table

    def seed_demo(self, count: int = 12) -> int:
        existing = self.list_records()
        if existing:
            return 0
        created = 0
        samples = self.demo_payloads(count)
        for payload in samples:
            row, errors = self.create(payload)
            if row and not errors:
                created += 1
        return created

    def demo_payloads(self, count: int) -> list[dict[str, Any]]:
        payloads: list[dict[str, Any]] = []
        for index in range(count):
            item: dict[str, Any] = {
                'status': STATUSES[index % len(STATUSES)],
            }
            item['workflow_key'] = f'Demo Workflow Key ' + str(index + 1) + ' workflow_defs'
            item['name'] = f'Demo Name ' + str(index + 1) + ' workflow_defs'
            item['trigger_event'] = f'Demo Trigger Event ' + str(index + 1) + ' workflow_defs'
            item['step_count'] = 10 + (index * 17) % 900 + (18)
            payloads.append(item)
        return payloads


engine = WorkflowDefsEngine()


def workflow_defs_concentration(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    """Count distinct workflow_defs values for a breakdown field."""
    tallies: dict[str, int] = {}
    for row in rows:
        label = str(row.get(field) or 'unspecified')
        tallies[label] = tallies.get(label, 0) + 1
    return dict(sorted(tallies.items(), key=lambda pair: pair[1], reverse=True))


def workflow_defs_watchlist(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return workflow_defs rows that operators should inspect this shift."""
    watched = []
    for row in rows:
        score = int(row.get('health_score') or 0)
        status = str(row.get('status') or '')
        if score < 50 or status == 'paused':
            watched.append(row)
    return watched[:25]


def workflow_defs_trend_stub(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets = {'week_0': 0, 'week_1': 0, 'week_2': 0, 'week_3': 0}
    for row in rows:
        stamp = str(row.get('created_at') or '')
        digit = 0
        for ch in stamp:
            if ch.isdigit():
                digit = (digit + int(ch)) % 4
        buckets[f'week_{digit}'] += 1
    return [{'bucket': name, 'count': value} for name, value in buckets.items()]


def explain_workflow_defs_score(row: dict[str, Any]) -> list[str]:
    notes = []
    score = int(row.get('health_score') or 0)
    if score >= 80:
        notes.append('This Workflow Studio record is operating inside the healthy band.')
    elif score >= 55:
        notes.append('Score is acceptable; schedule a light review on the next stand-up.')
    else:
        notes.append('Score is weak; assign an owner before the next control window.')
    status = str(row.get('status') or '')
    notes.append(f'Current lifecycle state is {status}.')
    notes.append('Fingerprint ' + str(row.get('integrity_hash') or 'n/a') + ' binds the field set.')
    return notes

def describe_workflow_defs_workflow_key(value: Any) -> str:
    """Operator hint for Workflow Key on Workflow Studio."""
    text = str(value or '').strip()
    if not text:
        return 'Required field workflow_key is empty for workflow_defs.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'workflow_key' + ' is zero; confirm that is intentional for Workflow Studio.'
        return 'workflow_key' + ' holds ' + str(number) + ' in the workflow_defs ledger.'
    if len(text) < 3:
        return 'workflow_key' + ' is unusually short; operators may misread the workflow_defs list.'
    return 'workflow_key' + ' is populated (' + str(len(text)) + ' chars) for workflow_defs.'


def describe_workflow_defs_name(value: Any) -> str:
    """Operator hint for Name on Workflow Studio."""
    text = str(value or '').strip()
    if not text:
        return 'Required field name is empty for workflow_defs.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'name' + ' is zero; confirm that is intentional for Workflow Studio.'
        return 'name' + ' holds ' + str(number) + ' in the workflow_defs ledger.'
    if len(text) < 3:
        return 'name' + ' is unusually short; operators may misread the workflow_defs list.'
    return 'name' + ' is populated (' + str(len(text)) + ' chars) for workflow_defs.'


def describe_workflow_defs_trigger_event(value: Any) -> str:
    """Operator hint for Trigger Event on Workflow Studio."""
    text = str(value or '').strip()
    if not text:
        return 'Required field trigger_event is empty for workflow_defs.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'trigger_event' + ' is zero; confirm that is intentional for Workflow Studio.'
        return 'trigger_event' + ' holds ' + str(number) + ' in the workflow_defs ledger.'
    if len(text) < 3:
        return 'trigger_event' + ' is unusually short; operators may misread the workflow_defs list.'
    return 'trigger_event' + ' is populated (' + str(len(text)) + ' chars) for workflow_defs.'


def describe_workflow_defs_step_count(value: Any) -> str:
    """Operator hint for Step Count on Workflow Studio."""
    text = str(value or '').strip()
    if not text:
        return 'Required field step_count is empty for workflow_defs.'
    if 'int' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'step_count' + ' is zero; confirm that is intentional for Workflow Studio.'
        return 'step_count' + ' holds ' + str(number) + ' in the workflow_defs ledger.'
    if len(text) < 3:
        return 'step_count' + ' is unusually short; operators may misread the workflow_defs list.'
    return 'step_count' + ' is populated (' + str(len(text)) + ' chars) for workflow_defs.'


def describe_workflow_defs_status(value: Any) -> str:
    """Operator hint for Status on Workflow Studio."""
    text = str(value or '').strip()
    if not text:
        return 'Required field status is empty for workflow_defs.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'status' + ' is zero; confirm that is intentional for Workflow Studio.'
        return 'status' + ' holds ' + str(number) + ' in the workflow_defs ledger.'
    if len(text) < 3:
        return 'status' + ' is unusually short; operators may misread the workflow_defs list.'
    return 'status' + ' is populated (' + str(len(text)) + ' chars) for workflow_defs.'


