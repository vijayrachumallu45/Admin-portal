"""Business engine for On-call Rotations.

Follow-the-sun coverage with primary and backup.
This module is the operational core for list, mutate, score, and export.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timedelta
from typing import Any

from app.storage import store

DOMAIN_KEY = 'oncall_rotations'
DOMAIN_TITLE = 'On-call Rotations'
STATUSES = ['scheduled', 'active', 'complete']
REQUIRED = ['rotation', 'primary_name', 'backup_name', 'starts_on', 'status']
FIELD_TYPES = { 'rotation': 'str', 'primary_name': 'str', 'backup_name': 'str', 'starts_on': 'date', 'status': 'str' }


def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == '':
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


class OncallRotationsRecord(dict):
    """Typed-ish mapping for oncall_rotations rows used by templates and exports."""

    def display_title(self) -> str:
        return str(self.get('rotation') or self.get('id') or 'untitled')


class OncallRotationsEngine:
    """CRUD, validation, scoring, and period reports for On-call Rotations."""

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
        text_rotation = str(payload.get('rotation') or '').strip()
        if len(text_rotation) > 240:
            errors.append('rotation' + ' is longer than the 240 character ledger cap')
        if text_rotation and text_rotation.startswith(' '):
            errors.append('rotation' + ' cannot start with whitespace')
        text_primary_name = str(payload.get('primary_name') or '').strip()
        if len(text_primary_name) > 240:
            errors.append('primary_name' + ' is longer than the 240 character ledger cap')
        if text_primary_name and text_primary_name.startswith(' '):
            errors.append('primary_name' + ' cannot start with whitespace')
        text_backup_name = str(payload.get('backup_name') or '').strip()
        if len(text_backup_name) > 240:
            errors.append('backup_name' + ' is longer than the 240 character ledger cap')
        if text_backup_name and text_backup_name.startswith(' '):
            errors.append('backup_name' + ' cannot start with whitespace')
        date_starts_on = str(payload.get('starts_on') or '').strip()
        if date_starts_on:
            try:
                date.fromisoformat(date_starts_on)
            except ValueError:
                errors.append('starts_on' + ' must use ISO date format YYYY-MM-DD')
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
        row['rotation'] = str(payload.get('rotation') or '').strip()
        row['primary_name'] = str(payload.get('primary_name') or '').strip()
        row['backup_name'] = str(payload.get('backup_name') or '').strip()
        row['starts_on'] = str(payload.get('starts_on') or '').strip()
        row['status'] = str(payload.get('status') or '').strip()
        if not row.get('status'):
            row['status'] = 'scheduled'
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
        return f'oncall_rotations-' + format(total, '06x')

    def health_score(self, row: dict[str, Any]) -> int:
        score = 40
        status = str(row.get('status') or '')
        if status == 'scheduled':
            score += 8
        if status == 'complete':
            score -= 12
        text_rotation = str(row.get('rotation') or '')
        if text_rotation:
            score += min(10, len(text_rotation) // 8)
            if text_rotation[:1].isupper():
                score += 2
        text_primary_name = str(row.get('primary_name') or '')
        if text_primary_name:
            score += min(10, len(text_primary_name) // 8)
            if text_primary_name[:1].isupper():
                score += 2
        text_backup_name = str(row.get('backup_name') or '')
        if text_backup_name:
            score += min(10, len(text_backup_name) // 8)
            if text_backup_name[:1].isupper():
                score += 2
        text_starts_on = str(row.get('starts_on') or '')
        if text_starts_on:
            score += min(10, len(text_starts_on) // 8)
            if text_starts_on[:1].isupper():
                score += 2
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
            item['rotation'] = f'Demo Rotation ' + str(index + 1) + ' oncall_rotations'
            item['primary_name'] = f'Demo Primary Name ' + str(index + 1) + ' oncall_rotations'
            item['backup_name'] = f'Demo Backup Name ' + str(index + 1) + ' oncall_rotations'
            item['starts_on'] = (date.today() + timedelta(days=(index % 40) - 8)).isoformat()
            payloads.append(item)
        return payloads


engine = OncallRotationsEngine()


def oncall_rotations_concentration(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    """Count distinct oncall_rotations values for a breakdown field."""
    tallies: dict[str, int] = {}
    for row in rows:
        label = str(row.get(field) or 'unspecified')
        tallies[label] = tallies.get(label, 0) + 1
    return dict(sorted(tallies.items(), key=lambda pair: pair[1], reverse=True))


def oncall_rotations_watchlist(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return oncall_rotations rows that operators should inspect this shift."""
    watched = []
    for row in rows:
        score = int(row.get('health_score') or 0)
        status = str(row.get('status') or '')
        if score < 50 or status == 'complete':
            watched.append(row)
    return watched[:25]


def oncall_rotations_trend_stub(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets = {'week_0': 0, 'week_1': 0, 'week_2': 0, 'week_3': 0}
    for row in rows:
        stamp = str(row.get('created_at') or '')
        digit = 0
        for ch in stamp:
            if ch.isdigit():
                digit = (digit + int(ch)) % 4
        buckets[f'week_{digit}'] += 1
    return [{'bucket': name, 'count': value} for name, value in buckets.items()]


def explain_oncall_rotations_score(row: dict[str, Any]) -> list[str]:
    notes = []
    score = int(row.get('health_score') or 0)
    if score >= 80:
        notes.append('This On-call Rotations record is operating inside the healthy band.')
    elif score >= 55:
        notes.append('Score is acceptable; schedule a light review on the next stand-up.')
    else:
        notes.append('Score is weak; assign an owner before the next control window.')
    status = str(row.get('status') or '')
    notes.append(f'Current lifecycle state is {status}.')
    notes.append('Fingerprint ' + str(row.get('integrity_hash') or 'n/a') + ' binds the field set.')
    return notes

def describe_oncall_rotations_rotation(value: Any) -> str:
    """Operator hint for Rotation on On-call Rotations."""
    text = str(value or '').strip()
    if not text:
        return 'Required field rotation is empty for oncall_rotations.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'rotation' + ' is zero; confirm that is intentional for On-call Rotations.'
        return 'rotation' + ' holds ' + str(number) + ' in the oncall_rotations ledger.'
    if len(text) < 3:
        return 'rotation' + ' is unusually short; operators may misread the oncall_rotations list.'
    return 'rotation' + ' is populated (' + str(len(text)) + ' chars) for oncall_rotations.'


def describe_oncall_rotations_primary_name(value: Any) -> str:
    """Operator hint for Primary Name on On-call Rotations."""
    text = str(value or '').strip()
    if not text:
        return 'Required field primary_name is empty for oncall_rotations.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'primary_name' + ' is zero; confirm that is intentional for On-call Rotations.'
        return 'primary_name' + ' holds ' + str(number) + ' in the oncall_rotations ledger.'
    if len(text) < 3:
        return 'primary_name' + ' is unusually short; operators may misread the oncall_rotations list.'
    return 'primary_name' + ' is populated (' + str(len(text)) + ' chars) for oncall_rotations.'


def describe_oncall_rotations_backup_name(value: Any) -> str:
    """Operator hint for Backup Name on On-call Rotations."""
    text = str(value or '').strip()
    if not text:
        return 'Required field backup_name is empty for oncall_rotations.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'backup_name' + ' is zero; confirm that is intentional for On-call Rotations.'
        return 'backup_name' + ' holds ' + str(number) + ' in the oncall_rotations ledger.'
    if len(text) < 3:
        return 'backup_name' + ' is unusually short; operators may misread the oncall_rotations list.'
    return 'backup_name' + ' is populated (' + str(len(text)) + ' chars) for oncall_rotations.'


def describe_oncall_rotations_starts_on(value: Any) -> str:
    """Operator hint for Starts On on On-call Rotations."""
    text = str(value or '').strip()
    if not text:
        return 'Required field starts_on is empty for oncall_rotations.'
    if 'date' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'starts_on' + ' is zero; confirm that is intentional for On-call Rotations.'
        return 'starts_on' + ' holds ' + str(number) + ' in the oncall_rotations ledger.'
    if len(text) < 3:
        return 'starts_on' + ' is unusually short; operators may misread the oncall_rotations list.'
    return 'starts_on' + ' is populated (' + str(len(text)) + ' chars) for oncall_rotations.'


def describe_oncall_rotations_status(value: Any) -> str:
    """Operator hint for Status on On-call Rotations."""
    text = str(value or '').strip()
    if not text:
        return 'Required field status is empty for oncall_rotations.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'status' + ' is zero; confirm that is intentional for On-call Rotations.'
        return 'status' + ' holds ' + str(number) + ' in the oncall_rotations ledger.'
    if len(text) < 3:
        return 'status' + ' is unusually short; operators may misread the oncall_rotations list.'
    return 'status' + ' is populated (' + str(len(text)) + ' chars) for oncall_rotations.'


