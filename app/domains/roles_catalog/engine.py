"""Business engine for Role Catalog.

Named permission bundles with risk ratings and approval owners.
This module is the operational core for list, mutate, score, and export.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timedelta
from typing import Any

from app.storage import store

DOMAIN_KEY = 'roles_catalog'
DOMAIN_TITLE = 'Role Catalog'
STATUSES = ['draft', 'published', 'deprecated']
REQUIRED = ['role_key', 'display_name', 'risk_level', 'owner_team', 'review_days', 'status']
FIELD_TYPES = { 'role_key': 'str', 'display_name': 'str', 'risk_level': 'str', 'owner_team': 'str', 'max_holders': 'int', 'review_days': 'int', 'status': 'str' }


def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == '':
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


class RolesCatalogRecord(dict):
    """Typed-ish mapping for roles_catalog rows used by templates and exports."""

    def display_title(self) -> str:
        return str(self.get('role_key') or self.get('id') or 'untitled')


class RolesCatalogEngine:
    """CRUD, validation, scoring, and period reports for Role Catalog."""

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
        text_role_key = str(payload.get('role_key') or '').strip()
        if len(text_role_key) > 240:
            errors.append('role_key' + ' is longer than the 240 character ledger cap')
        if text_role_key and text_role_key.startswith(' '):
            errors.append('role_key' + ' cannot start with whitespace')
        text_display_name = str(payload.get('display_name') or '').strip()
        if len(text_display_name) > 240:
            errors.append('display_name' + ' is longer than the 240 character ledger cap')
        if text_display_name and text_display_name.startswith(' '):
            errors.append('display_name' + ' cannot start with whitespace')
        text_risk_level = str(payload.get('risk_level') or '').strip()
        if len(text_risk_level) > 240:
            errors.append('risk_level' + ' is longer than the 240 character ledger cap')
        if text_risk_level and text_risk_level.startswith(' '):
            errors.append('risk_level' + ' cannot start with whitespace')
        text_owner_team = str(payload.get('owner_team') or '').strip()
        if len(text_owner_team) > 240:
            errors.append('owner_team' + ' is longer than the 240 character ledger cap')
        if text_owner_team and text_owner_team.startswith(' '):
            errors.append('owner_team' + ' cannot start with whitespace')
        raw_max_holders = payload.get('max_holders')
        if raw_max_holders not in (None, ''):
            try:
                number_max_holders = int(raw_max_holders)
            except (TypeError, ValueError):
                errors.append('max_holders' + ' must be a whole number')
            else:
                if number_max_holders < 0:
                    errors.append('max_holders' + ' cannot be negative in roles_catalog')
                if number_max_holders > 10_000_000_000:
                    errors.append('max_holders' + ' exceeds the operational ceiling')
        raw_review_days = payload.get('review_days')
        if raw_review_days not in (None, ''):
            try:
                number_review_days = int(raw_review_days)
            except (TypeError, ValueError):
                errors.append('review_days' + ' must be a whole number')
            else:
                if number_review_days < 0:
                    errors.append('review_days' + ' cannot be negative in roles_catalog')
                if number_review_days > 10_000_000_000:
                    errors.append('review_days' + ' exceeds the operational ceiling')
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
        row['role_key'] = str(payload.get('role_key') or '').strip()
        row['display_name'] = str(payload.get('display_name') or '').strip()
        row['risk_level'] = str(payload.get('risk_level') or '').strip()
        row['owner_team'] = str(payload.get('owner_team') or '').strip()
        row['max_holders'] = _as_int(payload.get('max_holders'))
        row['review_days'] = _as_int(payload.get('review_days'))
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
        return f'roles_catalog-' + format(total, '06x')

    def health_score(self, row: dict[str, Any]) -> int:
        score = 40
        status = str(row.get('status') or '')
        if status == 'draft':
            score += 8
        if status == 'deprecated':
            score -= 12
        text_role_key = str(row.get('role_key') or '')
        if text_role_key:
            score += min(10, len(text_role_key) // 8)
            if text_role_key[:1].isupper():
                score += 2
        text_display_name = str(row.get('display_name') or '')
        if text_display_name:
            score += min(10, len(text_display_name) // 8)
            if text_display_name[:1].isupper():
                score += 2
        text_risk_level = str(row.get('risk_level') or '')
        if text_risk_level:
            score += min(10, len(text_risk_level) // 8)
            if text_risk_level[:1].isupper():
                score += 2
        text_owner_team = str(row.get('owner_team') or '')
        if text_owner_team:
            score += min(10, len(text_owner_team) // 8)
            if text_owner_team[:1].isupper():
                score += 2
        value_max_holders = _as_int(row.get('max_holders'))
        if value_max_holders == 0:
            score -= 4
        elif value_max_holders < 10:
            score += 3
        elif value_max_holders < 1000:
            score += 6
        else:
            score += 9
        score += min(15, value_max_holders % 17)
        value_review_days = _as_int(row.get('review_days'))
        if value_review_days == 0:
            score -= 4
        elif value_review_days < 10:
            score += 3
        elif value_review_days < 1000:
            score += 6
        else:
            score += 9
        score += min(15, value_review_days % 17)
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
            item['role_key'] = f'Demo Role Key ' + str(index + 1) + ' roles_catalog'
            item['display_name'] = f'Demo Display Name ' + str(index + 1) + ' roles_catalog'
            item['risk_level'] = f'Demo Risk Level ' + str(index + 1) + ' roles_catalog'
            item['owner_team'] = f'Demo Owner Team ' + str(index + 1) + ' roles_catalog'
            item['max_holders'] = 10 + (index * 17) % 900 + (39)
            item['review_days'] = 10 + (index * 17) % 900 + (24)
            payloads.append(item)
        return payloads


engine = RolesCatalogEngine()


def roles_catalog_concentration(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    """Count distinct roles_catalog values for a breakdown field."""
    tallies: dict[str, int] = {}
    for row in rows:
        label = str(row.get(field) or 'unspecified')
        tallies[label] = tallies.get(label, 0) + 1
    return dict(sorted(tallies.items(), key=lambda pair: pair[1], reverse=True))


def roles_catalog_watchlist(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return roles_catalog rows that operators should inspect this shift."""
    watched = []
    for row in rows:
        score = int(row.get('health_score') or 0)
        status = str(row.get('status') or '')
        if score < 50 or status == 'deprecated':
            watched.append(row)
    return watched[:25]


def roles_catalog_trend_stub(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets = {'week_0': 0, 'week_1': 0, 'week_2': 0, 'week_3': 0}
    for row in rows:
        stamp = str(row.get('created_at') or '')
        digit = 0
        for ch in stamp:
            if ch.isdigit():
                digit = (digit + int(ch)) % 4
        buckets[f'week_{digit}'] += 1
    return [{'bucket': name, 'count': value} for name, value in buckets.items()]


def explain_roles_catalog_score(row: dict[str, Any]) -> list[str]:
    notes = []
    score = int(row.get('health_score') or 0)
    if score >= 80:
        notes.append('This Role Catalog record is operating inside the healthy band.')
    elif score >= 55:
        notes.append('Score is acceptable; schedule a light review on the next stand-up.')
    else:
        notes.append('Score is weak; assign an owner before the next control window.')
    status = str(row.get('status') or '')
    notes.append(f'Current lifecycle state is {status}.')
    notes.append('Fingerprint ' + str(row.get('integrity_hash') or 'n/a') + ' binds the field set.')
    return notes

def describe_roles_catalog_role_key(value: Any) -> str:
    """Operator hint for Role Key on Role Catalog."""
    text = str(value or '').strip()
    if not text:
        return 'Required field role_key is empty for roles_catalog.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'role_key' + ' is zero; confirm that is intentional for Role Catalog.'
        return 'role_key' + ' holds ' + str(number) + ' in the roles_catalog ledger.'
    if len(text) < 3:
        return 'role_key' + ' is unusually short; operators may misread the roles_catalog list.'
    return 'role_key' + ' is populated (' + str(len(text)) + ' chars) for roles_catalog.'


def describe_roles_catalog_display_name(value: Any) -> str:
    """Operator hint for Display Name on Role Catalog."""
    text = str(value or '').strip()
    if not text:
        return 'Required field display_name is empty for roles_catalog.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'display_name' + ' is zero; confirm that is intentional for Role Catalog.'
        return 'display_name' + ' holds ' + str(number) + ' in the roles_catalog ledger.'
    if len(text) < 3:
        return 'display_name' + ' is unusually short; operators may misread the roles_catalog list.'
    return 'display_name' + ' is populated (' + str(len(text)) + ' chars) for roles_catalog.'


def describe_roles_catalog_risk_level(value: Any) -> str:
    """Operator hint for Risk Level on Role Catalog."""
    text = str(value or '').strip()
    if not text:
        return 'Required field risk_level is empty for roles_catalog.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'risk_level' + ' is zero; confirm that is intentional for Role Catalog.'
        return 'risk_level' + ' holds ' + str(number) + ' in the roles_catalog ledger.'
    if len(text) < 3:
        return 'risk_level' + ' is unusually short; operators may misread the roles_catalog list.'
    return 'risk_level' + ' is populated (' + str(len(text)) + ' chars) for roles_catalog.'


def describe_roles_catalog_owner_team(value: Any) -> str:
    """Operator hint for Owner Team on Role Catalog."""
    text = str(value or '').strip()
    if not text:
        return 'Required field owner_team is empty for roles_catalog.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'owner_team' + ' is zero; confirm that is intentional for Role Catalog.'
        return 'owner_team' + ' holds ' + str(number) + ' in the roles_catalog ledger.'
    if len(text) < 3:
        return 'owner_team' + ' is unusually short; operators may misread the roles_catalog list.'
    return 'owner_team' + ' is populated (' + str(len(text)) + ' chars) for roles_catalog.'


def describe_roles_catalog_max_holders(value: Any) -> str:
    """Operator hint for Max Holders on Role Catalog."""
    text = str(value or '').strip()
    if not text:
        return 'Optional field max_holders is empty for roles_catalog.'
    if 'int' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'max_holders' + ' is zero; confirm that is intentional for Role Catalog.'
        return 'max_holders' + ' holds ' + str(number) + ' in the roles_catalog ledger.'
    if len(text) < 3:
        return 'max_holders' + ' is unusually short; operators may misread the roles_catalog list.'
    return 'max_holders' + ' is populated (' + str(len(text)) + ' chars) for roles_catalog.'


def describe_roles_catalog_review_days(value: Any) -> str:
    """Operator hint for Review Days on Role Catalog."""
    text = str(value or '').strip()
    if not text:
        return 'Required field review_days is empty for roles_catalog.'
    if 'int' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'review_days' + ' is zero; confirm that is intentional for Role Catalog.'
        return 'review_days' + ' holds ' + str(number) + ' in the roles_catalog ledger.'
    if len(text) < 3:
        return 'review_days' + ' is unusually short; operators may misread the roles_catalog list.'
    return 'review_days' + ' is populated (' + str(len(text)) + ' chars) for roles_catalog.'


def describe_roles_catalog_status(value: Any) -> str:
    """Operator hint for Status on Role Catalog."""
    text = str(value or '').strip()
    if not text:
        return 'Required field status is empty for roles_catalog.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'status' + ' is zero; confirm that is intentional for Role Catalog.'
        return 'status' + ' holds ' + str(number) + ' in the roles_catalog ledger.'
    if len(text) < 3:
        return 'status' + ' is unusually short; operators may misread the roles_catalog list.'
    return 'status' + ' is populated (' + str(len(text)) + ' chars) for roles_catalog.'


