"""Period reports and operator briefings for On-call Rotations."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.domains.oncall_rotations.queries import oncall_rotations_group_status, oncall_rotations_health_bands, oncall_rotations_completeness
from app.domains.oncall_rotations.policies import oncall_rotations_risk_band, oncall_rotations_sla_hours, oncall_rotations_owner_hint

DOMAIN_TITLE = 'On-call Rotations'


def oncall_rotations_age_days(row: dict[str, Any]) -> int:
    created = str(row.get('created_at') or '')
    try:
        parsed = datetime.fromisoformat(created.replace('Z', ''))
    except ValueError:
        return 0
    return max(0, (datetime.utcnow() - parsed).days)


def oncall_rotations_bucket(days: int) -> str:
    if days < 3:
        return 'fresh'
    if days < 14:
        return 'current'
    if days < 45:
        return 'aging'
    return 'legacy'


def oncall_rotations_line_item(row: dict[str, Any]) -> dict[str, Any]:
    days = oncall_rotations_age_days(row)
    return {
        'id': row.get('id'),
        'title': row.get('rotation'),
        'status': row.get('status'),
        'days': days,
        'bucket': oncall_rotations_bucket(days),
        'band': oncall_rotations_risk_band(row),
        'owner': oncall_rotations_owner_hint(row),
        'sla_hours': oncall_rotations_sla_hours(row),
        'completeness': oncall_rotations_completeness(row),
        'health_score': row.get('health_score'),
    }


def oncall_rotations_briefing(rows: list[dict[str, Any]]) -> dict[str, Any]:
    items = [oncall_rotations_line_item(row) for row in rows]
    by_bucket = {'fresh': 0, 'current': 0, 'aging': 0, 'legacy': 0}
    for item in items:
        by_bucket[str(item['bucket'])] += 1
    return {
        'title': DOMAIN_TITLE,
        'generated_at': datetime.utcnow().replace(microsecond=0).isoformat() + 'Z',
        'count': len(items),
        'bands': oncall_rotations_health_bands(rows),
        'buckets': by_bucket,
        'headline': oncall_rotations_headline(rows),
        'items': items[:40],
    }


def oncall_rotations_headline(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return 'On-call Rotations has no rows in the local ledger yet.'
    bands = oncall_rotations_health_bands(rows)
    critical = bands.get('critical', 0)
    if critical:
        return f'On-call Rotations: {critical} critical records need a named owner this shift.'
    return f'On-call Rotations: {len(rows)} records are inside the operating range.'


def oncall_rotations_csv_lines(rows: list[dict[str, Any]]) -> list[str]:
    header = ['id', 'title', 'status', 'days', 'bucket', 'band', 'owner', 'health_score']
    lines = [','.join(header)]
    for row in rows:
        item = oncall_rotations_line_item(row)
        lines.append(','.join(str(item.get(col, '')).replace(',', ' ') for col in header))
    return lines


def oncall_rotations_status_share(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped = oncall_rotations_group_status(rows)
    total = max(1, len(rows))
    share = []
    for status in ['scheduled', 'active', 'complete']:
        count = len(grouped.get(status, []))
        share.append({'status': status, 'count': count, 'pct': int((count / total) * 100)})
    return share


def oncall_rotations_owner_load(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    load: dict[str, int] = {}
    for row in rows:
        owner = oncall_rotations_owner_hint(row)
        load[owner] = load.get(owner, 0) + 1
    ranked = sorted(load.items(), key=lambda pair: pair[1], reverse=True)
    return [{'owner': name, 'count': count} for name, count in ranked]


def oncall_rotations_weekly_story(rows: list[dict[str, Any]]) -> list[str]:
    story = []
    briefing = oncall_rotations_briefing(rows)
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
    story.append('On-call Rotations briefing is local-only and does not call an external network.')
    return story


def oncall_rotations_print_pack(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'briefing': oncall_rotations_briefing(rows),
        'share': oncall_rotations_status_share(rows),
        'owners': oncall_rotations_owner_load(rows),
        'story': oncall_rotations_weekly_story(rows),
    }


class OncallRotationsReporter:
    """Builds operator-facing packs for On-call Rotations."""

    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.rows = list(rows or [])

    def refresh(self, rows: list[dict[str, Any]]) -> None:
        self.rows = list(rows)

    def briefing(self) -> dict[str, Any]:
        return oncall_rotations_briefing(self.rows)

    def story(self) -> list[str]:
        return oncall_rotations_weekly_story(self.rows)

    def csv(self) -> str:
        return '\n'.join(oncall_rotations_csv_lines(self.rows)) + '\n'

    def pack(self) -> dict[str, Any]:
        return oncall_rotations_print_pack(self.rows)


def build_oncall_rotations_reporter(rows: list[dict[str, Any]]) -> OncallRotationsReporter:
    return OncallRotationsReporter(rows)

def oncall_rotations_report_by_rotation(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice On-call Rotations by Rotation."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('rotation') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'rotation'} for label, count in ranked]


def oncall_rotations_report_by_primary_name(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice On-call Rotations by Primary Name."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('primary_name') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'primary_name'} for label, count in ranked]


def oncall_rotations_report_by_backup_name(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice On-call Rotations by Backup Name."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('backup_name') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'backup_name'} for label, count in ranked]


def oncall_rotations_report_by_starts_on(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice On-call Rotations by Starts On."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('starts_on') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'starts_on'} for label, count in ranked]


def oncall_rotations_report_by_status(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice On-call Rotations by Status."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('status') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'status'} for label, count in ranked]


