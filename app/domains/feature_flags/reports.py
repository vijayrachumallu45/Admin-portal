"""Period reports and operator briefings for Feature Flags."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.domains.feature_flags.queries import feature_flags_group_status, feature_flags_health_bands, feature_flags_completeness
from app.domains.feature_flags.policies import feature_flags_risk_band, feature_flags_sla_hours, feature_flags_owner_hint

DOMAIN_TITLE = 'Feature Flags'


def feature_flags_age_days(row: dict[str, Any]) -> int:
    created = str(row.get('created_at') or '')
    try:
        parsed = datetime.fromisoformat(created.replace('Z', ''))
    except ValueError:
        return 0
    return max(0, (datetime.utcnow() - parsed).days)


def feature_flags_bucket(days: int) -> str:
    if days < 3:
        return 'fresh'
    if days < 14:
        return 'current'
    if days < 45:
        return 'aging'
    return 'legacy'


def feature_flags_line_item(row: dict[str, Any]) -> dict[str, Any]:
    days = feature_flags_age_days(row)
    return {
        'id': row.get('id'),
        'title': row.get('flag_key'),
        'status': row.get('status'),
        'days': days,
        'bucket': feature_flags_bucket(days),
        'band': feature_flags_risk_band(row),
        'owner': feature_flags_owner_hint(row),
        'sla_hours': feature_flags_sla_hours(row),
        'completeness': feature_flags_completeness(row),
        'health_score': row.get('health_score'),
    }


def feature_flags_briefing(rows: list[dict[str, Any]]) -> dict[str, Any]:
    items = [feature_flags_line_item(row) for row in rows]
    by_bucket = {'fresh': 0, 'current': 0, 'aging': 0, 'legacy': 0}
    for item in items:
        by_bucket[str(item['bucket'])] += 1
    return {
        'title': DOMAIN_TITLE,
        'generated_at': datetime.utcnow().replace(microsecond=0).isoformat() + 'Z',
        'count': len(items),
        'bands': feature_flags_health_bands(rows),
        'buckets': by_bucket,
        'headline': feature_flags_headline(rows),
        'items': items[:40],
    }


def feature_flags_headline(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return 'Feature Flags has no rows in the local ledger yet.'
    bands = feature_flags_health_bands(rows)
    critical = bands.get('critical', 0)
    if critical:
        return f'Feature Flags: {critical} critical records need a named owner this shift.'
    return f'Feature Flags: {len(rows)} records are inside the operating range.'


def feature_flags_csv_lines(rows: list[dict[str, Any]]) -> list[str]:
    header = ['id', 'title', 'status', 'days', 'bucket', 'band', 'owner', 'health_score']
    lines = [','.join(header)]
    for row in rows:
        item = feature_flags_line_item(row)
        lines.append(','.join(str(item.get(col, '')).replace(',', ' ') for col in header))
    return lines


def feature_flags_status_share(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped = feature_flags_group_status(rows)
    total = max(1, len(rows))
    share = []
    for status in ['off', 'ramp', 'on', 'retired']:
        count = len(grouped.get(status, []))
        share.append({'status': status, 'count': count, 'pct': int((count / total) * 100)})
    return share


def feature_flags_owner_load(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    load: dict[str, int] = {}
    for row in rows:
        owner = feature_flags_owner_hint(row)
        load[owner] = load.get(owner, 0) + 1
    ranked = sorted(load.items(), key=lambda pair: pair[1], reverse=True)
    return [{'owner': name, 'count': count} for name, count in ranked]


def feature_flags_weekly_story(rows: list[dict[str, Any]]) -> list[str]:
    story = []
    briefing = feature_flags_briefing(rows)
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
    story.append('Feature Flags briefing is local-only and does not call an external network.')
    return story


def feature_flags_print_pack(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'briefing': feature_flags_briefing(rows),
        'share': feature_flags_status_share(rows),
        'owners': feature_flags_owner_load(rows),
        'story': feature_flags_weekly_story(rows),
    }


class FeatureFlagsReporter:
    """Builds operator-facing packs for Feature Flags."""

    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.rows = list(rows or [])

    def refresh(self, rows: list[dict[str, Any]]) -> None:
        self.rows = list(rows)

    def briefing(self) -> dict[str, Any]:
        return feature_flags_briefing(self.rows)

    def story(self) -> list[str]:
        return feature_flags_weekly_story(self.rows)

    def csv(self) -> str:
        return '\n'.join(feature_flags_csv_lines(self.rows)) + '\n'

    def pack(self) -> dict[str, Any]:
        return feature_flags_print_pack(self.rows)


def build_feature_flags_reporter(rows: list[dict[str, Any]]) -> FeatureFlagsReporter:
    return FeatureFlagsReporter(rows)

def feature_flags_report_by_flag_key(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Feature Flags by Flag Key."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('flag_key') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'flag_key'} for label, count in ranked]


def feature_flags_report_by_description(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Feature Flags by Description."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('description') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'description'} for label, count in ranked]


def feature_flags_report_by_percent(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Feature Flags by Percent."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('percent') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'percent'} for label, count in ranked]


def feature_flags_outlier_percent(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    values = []
    for row in rows:
        try:
            values.append(int(row.get('percent') or 0))
        except (TypeError, ValueError):
            values.append(0)
    if not values:
        return []
    avg = sum(values) / len(values)
    flagged = []
    for row, value in zip(rows, values):
        if value > avg * 3 and value > 0:
            flagged.append({'id': row.get('id'), 'field': 'percent', 'value': value, 'avg': int(avg)})
    return flagged


def feature_flags_report_by_owner(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Feature Flags by Owner."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('owner') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'owner'} for label, count in ranked]


def feature_flags_report_by_status(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Feature Flags by Status."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('status') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'status'} for label, count in ranked]


