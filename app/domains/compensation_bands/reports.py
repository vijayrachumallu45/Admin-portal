"""Period reports and operator briefings for Compensation Bands."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.domains.compensation_bands.queries import compensation_bands_group_status, compensation_bands_health_bands, compensation_bands_completeness
from app.domains.compensation_bands.policies import compensation_bands_risk_band, compensation_bands_sla_hours, compensation_bands_owner_hint

DOMAIN_TITLE = 'Compensation Bands'


def compensation_bands_age_days(row: dict[str, Any]) -> int:
    created = str(row.get('created_at') or '')
    try:
        parsed = datetime.fromisoformat(created.replace('Z', ''))
    except ValueError:
        return 0
    return max(0, (datetime.utcnow() - parsed).days)


def compensation_bands_bucket(days: int) -> str:
    if days < 3:
        return 'fresh'
    if days < 14:
        return 'current'
    if days < 45:
        return 'aging'
    return 'legacy'


def compensation_bands_line_item(row: dict[str, Any]) -> dict[str, Any]:
    days = compensation_bands_age_days(row)
    return {
        'id': row.get('id'),
        'title': row.get('band_code'),
        'status': row.get('status'),
        'days': days,
        'bucket': compensation_bands_bucket(days),
        'band': compensation_bands_risk_band(row),
        'owner': compensation_bands_owner_hint(row),
        'sla_hours': compensation_bands_sla_hours(row),
        'completeness': compensation_bands_completeness(row),
        'health_score': row.get('health_score'),
    }


def compensation_bands_briefing(rows: list[dict[str, Any]]) -> dict[str, Any]:
    items = [compensation_bands_line_item(row) for row in rows]
    by_bucket = {'fresh': 0, 'current': 0, 'aging': 0, 'legacy': 0}
    for item in items:
        by_bucket[str(item['bucket'])] += 1
    return {
        'title': DOMAIN_TITLE,
        'generated_at': datetime.utcnow().replace(microsecond=0).isoformat() + 'Z',
        'count': len(items),
        'bands': compensation_bands_health_bands(rows),
        'buckets': by_bucket,
        'headline': compensation_bands_headline(rows),
        'items': items[:40],
    }


def compensation_bands_headline(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return 'Compensation Bands has no rows in the local ledger yet.'
    bands = compensation_bands_health_bands(rows)
    critical = bands.get('critical', 0)
    if critical:
        return f'Compensation Bands: {critical} critical records need a named owner this shift.'
    return f'Compensation Bands: {len(rows)} records are inside the operating range.'


def compensation_bands_csv_lines(rows: list[dict[str, Any]]) -> list[str]:
    header = ['id', 'title', 'status', 'days', 'bucket', 'band', 'owner', 'health_score']
    lines = [','.join(header)]
    for row in rows:
        item = compensation_bands_line_item(row)
        lines.append(','.join(str(item.get(col, '')).replace(',', ' ') for col in header))
    return lines


def compensation_bands_status_share(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped = compensation_bands_group_status(rows)
    total = max(1, len(rows))
    share = []
    for status in ['draft', 'live', 'retired']:
        count = len(grouped.get(status, []))
        share.append({'status': status, 'count': count, 'pct': int((count / total) * 100)})
    return share


def compensation_bands_owner_load(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    load: dict[str, int] = {}
    for row in rows:
        owner = compensation_bands_owner_hint(row)
        load[owner] = load.get(owner, 0) + 1
    ranked = sorted(load.items(), key=lambda pair: pair[1], reverse=True)
    return [{'owner': name, 'count': count} for name, count in ranked]


def compensation_bands_weekly_story(rows: list[dict[str, Any]]) -> list[str]:
    story = []
    briefing = compensation_bands_briefing(rows)
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
    story.append('Compensation Bands briefing is local-only and does not call an external network.')
    return story


def compensation_bands_print_pack(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'briefing': compensation_bands_briefing(rows),
        'share': compensation_bands_status_share(rows),
        'owners': compensation_bands_owner_load(rows),
        'story': compensation_bands_weekly_story(rows),
    }


class CompensationBandsReporter:
    """Builds operator-facing packs for Compensation Bands."""

    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.rows = list(rows or [])

    def refresh(self, rows: list[dict[str, Any]]) -> None:
        self.rows = list(rows)

    def briefing(self) -> dict[str, Any]:
        return compensation_bands_briefing(self.rows)

    def story(self) -> list[str]:
        return compensation_bands_weekly_story(self.rows)

    def csv(self) -> str:
        return '\n'.join(compensation_bands_csv_lines(self.rows)) + '\n'

    def pack(self) -> dict[str, Any]:
        return compensation_bands_print_pack(self.rows)


def build_compensation_bands_reporter(rows: list[dict[str, Any]]) -> CompensationBandsReporter:
    return CompensationBandsReporter(rows)

def compensation_bands_report_by_band_code(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Compensation Bands by Band Code."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('band_code') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'band_code'} for label, count in ranked]


def compensation_bands_report_by_level_name(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Compensation Bands by Level Name."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('level_name') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'level_name'} for label, count in ranked]


def compensation_bands_report_by_min_cents(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Compensation Bands by Min Cents."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('min_cents') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'min_cents'} for label, count in ranked]


def compensation_bands_outlier_min_cents(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    values = []
    for row in rows:
        try:
            values.append(int(row.get('min_cents') or 0))
        except (TypeError, ValueError):
            values.append(0)
    if not values:
        return []
    avg = sum(values) / len(values)
    flagged = []
    for row, value in zip(rows, values):
        if value > avg * 3 and value > 0:
            flagged.append({'id': row.get('id'), 'field': 'min_cents', 'value': value, 'avg': int(avg)})
    return flagged


def compensation_bands_report_by_max_cents(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Compensation Bands by Max Cents."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('max_cents') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'max_cents'} for label, count in ranked]


def compensation_bands_outlier_max_cents(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    values = []
    for row in rows:
        try:
            values.append(int(row.get('max_cents') or 0))
        except (TypeError, ValueError):
            values.append(0)
    if not values:
        return []
    avg = sum(values) / len(values)
    flagged = []
    for row, value in zip(rows, values):
        if value > avg * 3 and value > 0:
            flagged.append({'id': row.get('id'), 'field': 'max_cents', 'value': value, 'avg': int(avg)})
    return flagged


def compensation_bands_report_by_status(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Compensation Bands by Status."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('status') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'status'} for label, count in ranked]


