"""Period reports and operator briefings for Field Events."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.domains.field_events.queries import field_events_group_status, field_events_health_bands, field_events_completeness
from app.domains.field_events.policies import field_events_risk_band, field_events_sla_hours, field_events_owner_hint

DOMAIN_TITLE = 'Field Events'


def field_events_age_days(row: dict[str, Any]) -> int:
    created = str(row.get('created_at') or '')
    try:
        parsed = datetime.fromisoformat(created.replace('Z', ''))
    except ValueError:
        return 0
    return max(0, (datetime.utcnow() - parsed).days)


def field_events_bucket(days: int) -> str:
    if days < 3:
        return 'fresh'
    if days < 14:
        return 'current'
    if days < 45:
        return 'aging'
    return 'legacy'


def field_events_line_item(row: dict[str, Any]) -> dict[str, Any]:
    days = field_events_age_days(row)
    return {
        'id': row.get('id'),
        'title': row.get('event_code'),
        'status': row.get('status'),
        'days': days,
        'bucket': field_events_bucket(days),
        'band': field_events_risk_band(row),
        'owner': field_events_owner_hint(row),
        'sla_hours': field_events_sla_hours(row),
        'completeness': field_events_completeness(row),
        'health_score': row.get('health_score'),
    }


def field_events_briefing(rows: list[dict[str, Any]]) -> dict[str, Any]:
    items = [field_events_line_item(row) for row in rows]
    by_bucket = {'fresh': 0, 'current': 0, 'aging': 0, 'legacy': 0}
    for item in items:
        by_bucket[str(item['bucket'])] += 1
    return {
        'title': DOMAIN_TITLE,
        'generated_at': datetime.utcnow().replace(microsecond=0).isoformat() + 'Z',
        'count': len(items),
        'bands': field_events_health_bands(rows),
        'buckets': by_bucket,
        'headline': field_events_headline(rows),
        'items': items[:40],
    }


def field_events_headline(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return 'Field Events has no rows in the local ledger yet.'
    bands = field_events_health_bands(rows)
    critical = bands.get('critical', 0)
    if critical:
        return f'Field Events: {critical} critical records need a named owner this shift.'
    return f'Field Events: {len(rows)} records are inside the operating range.'


def field_events_csv_lines(rows: list[dict[str, Any]]) -> list[str]:
    header = ['id', 'title', 'status', 'days', 'bucket', 'band', 'owner', 'health_score']
    lines = [','.join(header)]
    for row in rows:
        item = field_events_line_item(row)
        lines.append(','.join(str(item.get(col, '')).replace(',', ' ') for col in header))
    return lines


def field_events_status_share(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped = field_events_group_status(rows)
    total = max(1, len(rows))
    share = []
    for status in ['proposed', 'booked', 'live', 'wrap']:
        count = len(grouped.get(status, []))
        share.append({'status': status, 'count': count, 'pct': int((count / total) * 100)})
    return share


def field_events_owner_load(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    load: dict[str, int] = {}
    for row in rows:
        owner = field_events_owner_hint(row)
        load[owner] = load.get(owner, 0) + 1
    ranked = sorted(load.items(), key=lambda pair: pair[1], reverse=True)
    return [{'owner': name, 'count': count} for name, count in ranked]


def field_events_weekly_story(rows: list[dict[str, Any]]) -> list[str]:
    story = []
    briefing = field_events_briefing(rows)
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
    story.append('Field Events briefing is local-only and does not call an external network.')
    return story


def field_events_print_pack(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'briefing': field_events_briefing(rows),
        'share': field_events_status_share(rows),
        'owners': field_events_owner_load(rows),
        'story': field_events_weekly_story(rows),
    }


class FieldEventsReporter:
    """Builds operator-facing packs for Field Events."""

    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.rows = list(rows or [])

    def refresh(self, rows: list[dict[str, Any]]) -> None:
        self.rows = list(rows)

    def briefing(self) -> dict[str, Any]:
        return field_events_briefing(self.rows)

    def story(self) -> list[str]:
        return field_events_weekly_story(self.rows)

    def csv(self) -> str:
        return '\n'.join(field_events_csv_lines(self.rows)) + '\n'

    def pack(self) -> dict[str, Any]:
        return field_events_print_pack(self.rows)


def build_field_events_reporter(rows: list[dict[str, Any]]) -> FieldEventsReporter:
    return FieldEventsReporter(rows)

def field_events_report_by_event_code(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Field Events by Event Code."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('event_code') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'event_code'} for label, count in ranked]


def field_events_report_by_city(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Field Events by City."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('city') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'city'} for label, count in ranked]


def field_events_report_by_starts_on(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Field Events by Starts On."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('starts_on') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'starts_on'} for label, count in ranked]


def field_events_report_by_budget_cents(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Field Events by Budget Cents."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('budget_cents') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'budget_cents'} for label, count in ranked]


def field_events_outlier_budget_cents(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    values = []
    for row in rows:
        try:
            values.append(int(row.get('budget_cents') or 0))
        except (TypeError, ValueError):
            values.append(0)
    if not values:
        return []
    avg = sum(values) / len(values)
    flagged = []
    for row, value in zip(rows, values):
        if value > avg * 3 and value > 0:
            flagged.append({'id': row.get('id'), 'field': 'budget_cents', 'value': value, 'avg': int(avg)})
    return flagged


def field_events_report_by_status(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Field Events by Status."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('status') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'status'} for label, count in ranked]


