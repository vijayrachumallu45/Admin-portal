"""Period reports and operator briefings for Audit Ledger."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.domains.audit_events.queries import audit_events_group_status, audit_events_health_bands, audit_events_completeness
from app.domains.audit_events.policies import audit_events_risk_band, audit_events_sla_hours, audit_events_owner_hint

DOMAIN_TITLE = 'Audit Ledger'


def audit_events_age_days(row: dict[str, Any]) -> int:
    created = str(row.get('created_at') or '')
    try:
        parsed = datetime.fromisoformat(created.replace('Z', ''))
    except ValueError:
        return 0
    return max(0, (datetime.utcnow() - parsed).days)


def audit_events_bucket(days: int) -> str:
    if days < 3:
        return 'fresh'
    if days < 14:
        return 'current'
    if days < 45:
        return 'aging'
    return 'legacy'


def audit_events_line_item(row: dict[str, Any]) -> dict[str, Any]:
    days = audit_events_age_days(row)
    return {
        'id': row.get('id'),
        'title': row.get('actor'),
        'status': row.get('status'),
        'days': days,
        'bucket': audit_events_bucket(days),
        'band': audit_events_risk_band(row),
        'owner': audit_events_owner_hint(row),
        'sla_hours': audit_events_sla_hours(row),
        'completeness': audit_events_completeness(row),
        'health_score': row.get('health_score'),
    }


def audit_events_briefing(rows: list[dict[str, Any]]) -> dict[str, Any]:
    items = [audit_events_line_item(row) for row in rows]
    by_bucket = {'fresh': 0, 'current': 0, 'aging': 0, 'legacy': 0}
    for item in items:
        by_bucket[str(item['bucket'])] += 1
    return {
        'title': DOMAIN_TITLE,
        'generated_at': datetime.utcnow().replace(microsecond=0).isoformat() + 'Z',
        'count': len(items),
        'bands': audit_events_health_bands(rows),
        'buckets': by_bucket,
        'headline': audit_events_headline(rows),
        'items': items[:40],
    }


def audit_events_headline(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return 'Audit Ledger has no rows in the local ledger yet.'
    bands = audit_events_health_bands(rows)
    critical = bands.get('critical', 0)
    if critical:
        return f'Audit Ledger: {critical} critical records need a named owner this shift.'
    return f'Audit Ledger: {len(rows)} records are inside the operating range.'


def audit_events_csv_lines(rows: list[dict[str, Any]]) -> list[str]:
    header = ['id', 'title', 'status', 'days', 'bucket', 'band', 'owner', 'health_score']
    lines = [','.join(header)]
    for row in rows:
        item = audit_events_line_item(row)
        lines.append(','.join(str(item.get(col, '')).replace(',', ' ') for col in header))
    return lines


def audit_events_status_share(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped = audit_events_group_status(rows)
    total = max(1, len(rows))
    share = []
    for status in ['recorded', 'reviewed', 'escalated', 'closed']:
        count = len(grouped.get(status, []))
        share.append({'status': status, 'count': count, 'pct': int((count / total) * 100)})
    return share


def audit_events_owner_load(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    load: dict[str, int] = {}
    for row in rows:
        owner = audit_events_owner_hint(row)
        load[owner] = load.get(owner, 0) + 1
    ranked = sorted(load.items(), key=lambda pair: pair[1], reverse=True)
    return [{'owner': name, 'count': count} for name, count in ranked]


def audit_events_weekly_story(rows: list[dict[str, Any]]) -> list[str]:
    story = []
    briefing = audit_events_briefing(rows)
    story.append(str(briefing['headline']))
    story.append('Generated ' + str(briefing['generated_at']) + '.')
    bands = briefing['bands']
    story.append(
        'Bands — calm {calm}, watch {watch}, elevated {elevated}, critical {critical}.'.format(
            **bands
        )
    )
    buckets = briefing['buckets']
    story.append(
        'Age — fresh {fresh}, current {current}, aging {aging}, legacy {legacy}.'.format(
            **buckets
        )
    )
    story.append('Audit Ledger briefing is local-only and does not call an external network.')
    return story


def audit_events_print_pack(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'briefing': audit_events_briefing(rows),
        'share': audit_events_status_share(rows),
        'owners': audit_events_owner_load(rows),
        'story': audit_events_weekly_story(rows),
    }


class AuditEventsReporter:
    """Builds operator-facing packs for Audit Ledger."""

    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.rows = list(rows or [])

    def refresh(self, rows: list[dict[str, Any]]) -> None:
        self.rows = list(rows)

    def briefing(self) -> dict[str, Any]:
        return audit_events_briefing(self.rows)

    def story(self) -> list[str]:
        return audit_events_weekly_story(self.rows)

    def csv(self) -> str:
        return '\n'.join(audit_events_csv_lines(self.rows)) + '\n'

    def pack(self) -> dict[str, Any]:
        return audit_events_print_pack(self.rows)


def build_audit_events_reporter(rows: list[dict[str, Any]]) -> AuditEventsReporter:
    return AuditEventsReporter(rows)

def audit_events_report_by_actor(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Audit Ledger by Actor."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('actor') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'actor'} for label, count in ranked]


def audit_events_report_by_action(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Audit Ledger by Action."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('action') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'action'} for label, count in ranked]


def audit_events_report_by_resource(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Audit Ledger by Resource."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('resource') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'resource'} for label, count in ranked]


def audit_events_report_by_ip_hint(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Audit Ledger by Ip Hint."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('ip_hint') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'ip_hint'} for label, count in ranked]


def audit_events_report_by_occurred_at(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Audit Ledger by Occurred At."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('occurred_at') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'occurred_at'} for label, count in ranked]


def audit_events_report_by_severity(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Audit Ledger by Severity."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('severity') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'severity'} for label, count in ranked]


def audit_events_report_by_status(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Audit Ledger by Status."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('status') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'status'} for label, count in ranked]


