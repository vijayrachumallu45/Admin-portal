"""Period reports and operator briefings for Facilities."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.domains.facilities.queries import facilities_group_status, facilities_health_bands, facilities_completeness
from app.domains.facilities.policies import facilities_risk_band, facilities_sla_hours, facilities_owner_hint

DOMAIN_TITLE = 'Facilities'


def facilities_age_days(row: dict[str, Any]) -> int:
    created = str(row.get('created_at') or '')
    try:
        parsed = datetime.fromisoformat(created.replace('Z', ''))
    except ValueError:
        return 0
    return max(0, (datetime.utcnow() - parsed).days)


def facilities_bucket(days: int) -> str:
    if days < 3:
        return 'fresh'
    if days < 14:
        return 'current'
    if days < 45:
        return 'aging'
    return 'legacy'


def facilities_line_item(row: dict[str, Any]) -> dict[str, Any]:
    days = facilities_age_days(row)
    return {
        'id': row.get('id'),
        'title': row.get('site_code'),
        'status': row.get('status'),
        'days': days,
        'bucket': facilities_bucket(days),
        'band': facilities_risk_band(row),
        'owner': facilities_owner_hint(row),
        'sla_hours': facilities_sla_hours(row),
        'completeness': facilities_completeness(row),
        'health_score': row.get('health_score'),
    }


def facilities_briefing(rows: list[dict[str, Any]]) -> dict[str, Any]:
    items = [facilities_line_item(row) for row in rows]
    by_bucket = {'fresh': 0, 'current': 0, 'aging': 0, 'legacy': 0}
    for item in items:
        by_bucket[str(item['bucket'])] += 1
    return {
        'title': DOMAIN_TITLE,
        'generated_at': datetime.utcnow().replace(microsecond=0).isoformat() + 'Z',
        'count': len(items),
        'bands': facilities_health_bands(rows),
        'buckets': by_bucket,
        'headline': facilities_headline(rows),
        'items': items[:40],
    }


def facilities_headline(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return 'Facilities has no rows in the local ledger yet.'
    bands = facilities_health_bands(rows)
    critical = bands.get('critical', 0)
    if critical:
        return f'Facilities: {critical} critical records need a named owner this shift.'
    return f'Facilities: {len(rows)} records are inside the operating range.'


def facilities_csv_lines(rows: list[dict[str, Any]]) -> list[str]:
    header = ['id', 'title', 'status', 'days', 'bucket', 'band', 'owner', 'health_score']
    lines = [','.join(header)]
    for row in rows:
        item = facilities_line_item(row)
        lines.append(','.join(str(item.get(col, '')).replace(',', ' ') for col in header))
    return lines


def facilities_status_share(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped = facilities_group_status(rows)
    total = max(1, len(rows))
    share = []
    for status in ['open', 'limited', 'closed']:
        count = len(grouped.get(status, []))
        share.append({'status': status, 'count': count, 'pct': int((count / total) * 100)})
    return share


def facilities_owner_load(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    load: dict[str, int] = {}
    for row in rows:
        owner = facilities_owner_hint(row)
        load[owner] = load.get(owner, 0) + 1
    ranked = sorted(load.items(), key=lambda pair: pair[1], reverse=True)
    return [{'owner': name, 'count': count} for name, count in ranked]


def facilities_weekly_story(rows: list[dict[str, Any]]) -> list[str]:
    story = []
    briefing = facilities_briefing(rows)
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
    story.append('Facilities briefing is local-only and does not call an external network.')
    return story


def facilities_print_pack(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'briefing': facilities_briefing(rows),
        'share': facilities_status_share(rows),
        'owners': facilities_owner_load(rows),
        'story': facilities_weekly_story(rows),
    }


class FacilitiesReporter:
    """Builds operator-facing packs for Facilities."""

    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.rows = list(rows or [])

    def refresh(self, rows: list[dict[str, Any]]) -> None:
        self.rows = list(rows)

    def briefing(self) -> dict[str, Any]:
        return facilities_briefing(self.rows)

    def story(self) -> list[str]:
        return facilities_weekly_story(self.rows)

    def csv(self) -> str:
        return '\n'.join(facilities_csv_lines(self.rows)) + '\n'

    def pack(self) -> dict[str, Any]:
        return facilities_print_pack(self.rows)


def build_facilities_reporter(rows: list[dict[str, Any]]) -> FacilitiesReporter:
    return FacilitiesReporter(rows)

def facilities_report_by_site_code(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Facilities by Site Code."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('site_code') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'site_code'} for label, count in ranked]


def facilities_report_by_address(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Facilities by Address."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('address') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'address'} for label, count in ranked]


def facilities_report_by_capacity(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Facilities by Capacity."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('capacity') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'capacity'} for label, count in ranked]


def facilities_outlier_capacity(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    values = []
    for row in rows:
        try:
            values.append(int(row.get('capacity') or 0))
        except (TypeError, ValueError):
            values.append(0)
    if not values:
        return []
    avg = sum(values) / len(values)
    flagged = []
    for row, value in zip(rows, values):
        if value > avg * 3 and value > 0:
            flagged.append({'id': row.get('id'), 'field': 'capacity', 'value': value, 'avg': int(avg)})
    return flagged


def facilities_report_by_safety_owner(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Facilities by Safety Owner."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('safety_owner') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'safety_owner'} for label, count in ranked]


def facilities_report_by_status(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Facilities by Status."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('status') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'status'} for label, count in ranked]


