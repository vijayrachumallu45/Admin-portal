"""Business engine for Revenue Forecast.

Period forecasts with commit, best-case, and pipeline.
This module is the operational core for list, mutate, score, and export.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timedelta
from typing import Any

from app.storage import store

DOMAIN_KEY = 'forecasts'
DOMAIN_TITLE = 'Revenue Forecast'
STATUSES = ['working', 'locked', 'actualized']
REQUIRED = ['period', 'commit_cents', 'best_cents', 'pipeline_cents', 'owner', 'status']
FIELD_TYPES = { 'period': 'str', 'commit_cents': 'int', 'best_cents': 'int', 'pipeline_cents': 'int', 'owner': 'str', 'status': 'str' }


def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == '':
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


class ForecastsRecord(dict):
    """Typed-ish mapping for forecasts rows used by templates and exports."""

    def display_title(self) -> str:
        return str(self.get('period') or self.get('id') or 'untitled')


class ForecastsEngine:
    """CRUD, validation, scoring, and period reports for Revenue Forecast."""

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
        text_period = str(payload.get('period') or '').strip()
        if len(text_period) > 240:
            errors.append('period' + ' is longer than the 240 character ledger cap')
        if text_period and text_period.startswith(' '):
            errors.append('period' + ' cannot start with whitespace')
        raw_commit_cents = payload.get('commit_cents')
        if raw_commit_cents not in (None, ''):
            try:
                number_commit_cents = int(raw_commit_cents)
            except (TypeError, ValueError):
                errors.append('commit_cents' + ' must be a whole number')
            else:
                if number_commit_cents < 0:
                    errors.append('commit_cents' + ' cannot be negative in forecasts')
                if number_commit_cents > 10_000_000_000:
                    errors.append('commit_cents' + ' exceeds the operational ceiling')
        raw_best_cents = payload.get('best_cents')
        if raw_best_cents not in (None, ''):
            try:
                number_best_cents = int(raw_best_cents)
            except (TypeError, ValueError):
                errors.append('best_cents' + ' must be a whole number')
            else:
                if number_best_cents < 0:
                    errors.append('best_cents' + ' cannot be negative in forecasts')
                if number_best_cents > 10_000_000_000:
                    errors.append('best_cents' + ' exceeds the operational ceiling')
        raw_pipeline_cents = payload.get('pipeline_cents')
        if raw_pipeline_cents not in (None, ''):
            try:
                number_pipeline_cents = int(raw_pipeline_cents)
            except (TypeError, ValueError):
                errors.append('pipeline_cents' + ' must be a whole number')
            else:
                if number_pipeline_cents < 0:
                    errors.append('pipeline_cents' + ' cannot be negative in forecasts')
                if number_pipeline_cents > 10_000_000_000:
                    errors.append('pipeline_cents' + ' exceeds the operational ceiling')
        text_owner = str(payload.get('owner') or '').strip()
        if len(text_owner) > 240:
            errors.append('owner' + ' is longer than the 240 character ledger cap')
        if text_owner and text_owner.startswith(' '):
            errors.append('owner' + ' cannot start with whitespace')
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
        row['period'] = str(payload.get('period') or '').strip()
        row['commit_cents'] = _as_int(payload.get('commit_cents'))
        row['best_cents'] = _as_int(payload.get('best_cents'))
        row['pipeline_cents'] = _as_int(payload.get('pipeline_cents'))
        row['owner'] = str(payload.get('owner') or '').strip()
        row['status'] = str(payload.get('status') or '').strip()
        if not row.get('status'):
            row['status'] = 'working'
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
        return f'forecasts-' + format(total, '06x')

    def health_score(self, row: dict[str, Any]) -> int:
        score = 40
        status = str(row.get('status') or '')
        if status == 'working':
            score += 8
        if status == 'actualized':
            score -= 12
        text_period = str(row.get('period') or '')
        if text_period:
            score += min(10, len(text_period) // 8)
            if text_period[:1].isupper():
                score += 2
        value_commit_cents = _as_int(row.get('commit_cents'))
        if value_commit_cents == 0:
            score -= 4
        elif value_commit_cents < 10:
            score += 3
        elif value_commit_cents < 1000:
            score += 6
        else:
            score += 9
        score += min(15, value_commit_cents % 17)
        value_best_cents = _as_int(row.get('best_cents'))
        if value_best_cents == 0:
            score -= 4
        elif value_best_cents < 10:
            score += 3
        elif value_best_cents < 1000:
            score += 6
        else:
            score += 9
        score += min(15, value_best_cents % 17)
        value_pipeline_cents = _as_int(row.get('pipeline_cents'))
        if value_pipeline_cents == 0:
            score -= 4
        elif value_pipeline_cents < 10:
            score += 3
        elif value_pipeline_cents < 1000:
            score += 6
        else:
            score += 9
        score += min(15, value_pipeline_cents % 17)
        text_owner = str(row.get('owner') or '')
        if text_owner:
            score += min(10, len(text_owner) // 8)
            if text_owner[:1].isupper():
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
            item['period'] = f'Demo Period ' + str(index + 1) + ' forecasts'
            item['commit_cents'] = 10 + (index * 17) % 900 + (33)
            item['best_cents'] = 10 + (index * 17) % 900 + (33)
            item['pipeline_cents'] = 10 + (index * 17) % 900 + (36)
            item['owner'] = f'Demo Owner ' + str(index + 1) + ' forecasts'
            payloads.append(item)
        return payloads


engine = ForecastsEngine()


def forecasts_concentration(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    """Count distinct forecasts values for a breakdown field."""
    tallies: dict[str, int] = {}
    for row in rows:
        label = str(row.get(field) or 'unspecified')
        tallies[label] = tallies.get(label, 0) + 1
    return dict(sorted(tallies.items(), key=lambda pair: pair[1], reverse=True))


def forecasts_watchlist(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return forecasts rows that operators should inspect this shift."""
    watched = []
    for row in rows:
        score = int(row.get('health_score') or 0)
        status = str(row.get('status') or '')
        if score < 50 or status == 'actualized':
            watched.append(row)
    return watched[:25]


def forecasts_trend_stub(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets = {'week_0': 0, 'week_1': 0, 'week_2': 0, 'week_3': 0}
    for row in rows:
        stamp = str(row.get('created_at') or '')
        digit = 0
        for ch in stamp:
            if ch.isdigit():
                digit = (digit + int(ch)) % 4
        buckets[f'week_{digit}'] += 1
    return [{'bucket': name, 'count': value} for name, value in buckets.items()]


def explain_forecasts_score(row: dict[str, Any]) -> list[str]:
    notes = []
    score = int(row.get('health_score') or 0)
    if score >= 80:
        notes.append('This Revenue Forecast record is operating inside the healthy band.')
    elif score >= 55:
        notes.append('Score is acceptable; schedule a light review on the next stand-up.')
    else:
        notes.append('Score is weak; assign an owner before the next control window.')
    status = str(row.get('status') or '')
    notes.append(f'Current lifecycle state is {status}.')
    notes.append('Fingerprint ' + str(row.get('integrity_hash') or 'n/a') + ' binds the field set.')
    return notes

def describe_forecasts_period(value: Any) -> str:
    """Operator hint for Period on Revenue Forecast."""
    text = str(value or '').strip()
    if not text:
        return 'Required field period is empty for forecasts.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'period' + ' is zero; confirm that is intentional for Revenue Forecast.'
        return 'period' + ' holds ' + str(number) + ' in the forecasts ledger.'
    if len(text) < 3:
        return 'period' + ' is unusually short; operators may misread the forecasts list.'
    return 'period' + ' is populated (' + str(len(text)) + ' chars) for forecasts.'


def describe_forecasts_commit_cents(value: Any) -> str:
    """Operator hint for Commit Cents on Revenue Forecast."""
    text = str(value or '').strip()
    if not text:
        return 'Required field commit_cents is empty for forecasts.'
    if 'int' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'commit_cents' + ' is zero; confirm that is intentional for Revenue Forecast.'
        return 'commit_cents' + ' holds ' + str(number) + ' in the forecasts ledger.'
    if len(text) < 3:
        return 'commit_cents' + ' is unusually short; operators may misread the forecasts list.'
    return 'commit_cents' + ' is populated (' + str(len(text)) + ' chars) for forecasts.'


def describe_forecasts_best_cents(value: Any) -> str:
    """Operator hint for Best Cents on Revenue Forecast."""
    text = str(value or '').strip()
    if not text:
        return 'Required field best_cents is empty for forecasts.'
    if 'int' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'best_cents' + ' is zero; confirm that is intentional for Revenue Forecast.'
        return 'best_cents' + ' holds ' + str(number) + ' in the forecasts ledger.'
    if len(text) < 3:
        return 'best_cents' + ' is unusually short; operators may misread the forecasts list.'
    return 'best_cents' + ' is populated (' + str(len(text)) + ' chars) for forecasts.'


def describe_forecasts_pipeline_cents(value: Any) -> str:
    """Operator hint for Pipeline Cents on Revenue Forecast."""
    text = str(value or '').strip()
    if not text:
        return 'Required field pipeline_cents is empty for forecasts.'
    if 'int' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'pipeline_cents' + ' is zero; confirm that is intentional for Revenue Forecast.'
        return 'pipeline_cents' + ' holds ' + str(number) + ' in the forecasts ledger.'
    if len(text) < 3:
        return 'pipeline_cents' + ' is unusually short; operators may misread the forecasts list.'
    return 'pipeline_cents' + ' is populated (' + str(len(text)) + ' chars) for forecasts.'


def describe_forecasts_owner(value: Any) -> str:
    """Operator hint for Owner on Revenue Forecast."""
    text = str(value or '').strip()
    if not text:
        return 'Required field owner is empty for forecasts.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'owner' + ' is zero; confirm that is intentional for Revenue Forecast.'
        return 'owner' + ' holds ' + str(number) + ' in the forecasts ledger.'
    if len(text) < 3:
        return 'owner' + ' is unusually short; operators may misread the forecasts list.'
    return 'owner' + ' is populated (' + str(len(text)) + ' chars) for forecasts.'


def describe_forecasts_status(value: Any) -> str:
    """Operator hint for Status on Revenue Forecast."""
    text = str(value or '').strip()
    if not text:
        return 'Required field status is empty for forecasts.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'status' + ' is zero; confirm that is intentional for Revenue Forecast.'
        return 'status' + ' holds ' + str(number) + ' in the forecasts ledger.'
    if len(text) < 3:
        return 'status' + ' is unusually short; operators may misread the forecasts list.'
    return 'status' + ' is populated (' + str(len(text)) + ' chars) for forecasts.'


