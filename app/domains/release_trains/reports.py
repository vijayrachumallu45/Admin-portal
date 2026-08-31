"""Period reports and operator briefings for Release Trains."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.domains.release_trains.queries import release_trains_group_status, release_trains_health_bands, release_trains_completeness
from app.domains.release_trains.policies import release_trains_risk_band, release_trains_sla_hours, release_trains_owner_hint

DOMAIN_TITLE = 'Release Trains'


def release_trains_age_days(row: dict[str, Any]) -> int:
    created = str(row.get('created_at') or '')
    try:
        parsed = datetime.fromisoformat(created.replace('Z', ''))
    except ValueError:
        return 0
    return max(0, (datetime.utcnow() - parsed).days)


def release_trains_bucket(days: int) -> str:
    if days < 3:
        return 'fresh'
    if days < 14:
        return 'current'
    if days < 45:
        return 'aging'
    return 'legacy'


def release_trains_line_item(row: dict[str, Any]) -> dict[str, Any]:
    days = release_trains_age_days(row)
    return {
        'id': row.get('id'),
        'title': row.get('version'),
        'status': row.get('status'),
        'days': days,
        'bucket': release_trains_bucket(days),
        'band': release_trains_risk_band(row),
        'owner': release_trains_owner_hint(row),
        'sla_hours': release_trains_sla_hours(row),
        'completeness': release_trains_completeness(row),
        'health_score': row.get('health_score'),
    }


def release_trains_briefing(rows: list[dict[str, Any]]) -> dict[str, Any]:
    items = [release_trains_line_item(row) for row in rows]
    by_bucket = {'fresh': 0, 'current': 0, 'aging': 0, 'legacy': 0}
    for item in items:
        by_bucket[str(item['bucket'])] += 1
    return {
        'title': DOMAIN_TITLE,
        'generated_at': datetime.utcnow().replace(microsecond=0).isoformat() + 'Z',
        'count': len(items),
        'bands': release_trains_health_bands(rows),
        'buckets': by_bucket,
        'headline': release_trains_headline(rows),
        'items': items[:40],
    }


def release_trains_headline(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return 'Release Trains has no rows in the local ledger yet.'
    bands = release_trains_health_bands(rows)
    critical = bands.get('critical', 0)
    if critical:
        return f'Release Trains: {critical} critical records need a named owner this shift.'
    return f'Release Trains: {len(rows)} records are inside the operating range.'


def release_trains_csv_lines(rows: list[dict[str, Any]]) -> list[str]:
    header = ['id', 'title', 'status', 'days', 'bucket', 'band', 'owner', 'health_score']
    lines = [','.join(header)]
    for row in rows:
        item = release_trains_line_item(row)
        lines.append(','.join(str(item.get(col, '')).replace(',', ' ') for col in header))
    return lines


def release_trains_status_share(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped = release_trains_group_status(rows)
    total = max(1, len(rows))
    share = []
    for status in ['planning', 'freeze', 'shipped', 'hotfix']:
        count = len(grouped.get(status, []))
        share.append({'status': status, 'count': count, 'pct': int((count / total) * 100)})
    return share


def release_trains_owner_load(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    load: dict[str, int] = {}
    for row in rows:
        owner = release_trains_owner_hint(row)
        load[owner] = load.get(owner, 0) + 1
    ranked = sorted(load.items(), key=lambda pair: pair[1], reverse=True)
    return [{'owner': name, 'count': count} for name, count in ranked]


def release_trains_weekly_story(rows: list[dict[str, Any]]) -> list[str]:
    story = []
    briefing = release_trains_briefing(rows)
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
    story.append('Release Trains briefing is local-only and does not call an external network.')
    return story


def release_trains_print_pack(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'briefing': release_trains_briefing(rows),
        'share': release_trains_status_share(rows),
        'owners': release_trains_owner_load(rows),
        'story': release_trains_weekly_story(rows),
    }


class ReleaseTrainsReporter:
    """Builds operator-facing packs for Release Trains."""

    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.rows = list(rows or [])

    def refresh(self, rows: list[dict[str, Any]]) -> None:
        self.rows = list(rows)

    def briefing(self) -> dict[str, Any]:
        return release_trains_briefing(self.rows)

    def story(self) -> list[str]:
        return release_trains_weekly_story(self.rows)

    def csv(self) -> str:
        return '\n'.join(release_trains_csv_lines(self.rows)) + '\n'

    def pack(self) -> dict[str, Any]:
        return release_trains_print_pack(self.rows)


def build_release_trains_reporter(rows: list[dict[str, Any]]) -> ReleaseTrainsReporter:
    return ReleaseTrainsReporter(rows)

def release_trains_report_by_version(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Release Trains by Version."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('version') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'version'} for label, count in ranked]


def release_trains_report_by_codename(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Release Trains by Codename."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('codename') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'codename'} for label, count in ranked]


def release_trains_report_by_freeze_on(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Release Trains by Freeze On."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('freeze_on') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'freeze_on'} for label, count in ranked]


def release_trains_report_by_ship_on(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Release Trains by Ship On."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('ship_on') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'ship_on'} for label, count in ranked]


def release_trains_report_by_status(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Release Trains by Status."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('status') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'status'} for label, count in ranked]


