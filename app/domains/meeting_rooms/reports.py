"""Period reports and operator briefings for Meeting Rooms."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.domains.meeting_rooms.queries import meeting_rooms_group_status, meeting_rooms_health_bands, meeting_rooms_completeness
from app.domains.meeting_rooms.policies import meeting_rooms_risk_band, meeting_rooms_sla_hours, meeting_rooms_owner_hint

DOMAIN_TITLE = 'Meeting Rooms'


def meeting_rooms_age_days(row: dict[str, Any]) -> int:
    created = str(row.get('created_at') or '')
    try:
        parsed = datetime.fromisoformat(created.replace('Z', ''))
    except ValueError:
        return 0
    return max(0, (datetime.utcnow() - parsed).days)


def meeting_rooms_bucket(days: int) -> str:
    if days < 3:
        return 'fresh'
    if days < 14:
        return 'current'
    if days < 45:
        return 'aging'
    return 'legacy'


def meeting_rooms_line_item(row: dict[str, Any]) -> dict[str, Any]:
    days = meeting_rooms_age_days(row)
    return {
        'id': row.get('id'),
        'title': row.get('room_code'),
        'status': row.get('status'),
        'days': days,
        'bucket': meeting_rooms_bucket(days),
        'band': meeting_rooms_risk_band(row),
        'owner': meeting_rooms_owner_hint(row),
        'sla_hours': meeting_rooms_sla_hours(row),
        'completeness': meeting_rooms_completeness(row),
        'health_score': row.get('health_score'),
    }


def meeting_rooms_briefing(rows: list[dict[str, Any]]) -> dict[str, Any]:
    items = [meeting_rooms_line_item(row) for row in rows]
    by_bucket = {'fresh': 0, 'current': 0, 'aging': 0, 'legacy': 0}
    for item in items:
        by_bucket[str(item['bucket'])] += 1
    return {
        'title': DOMAIN_TITLE,
        'generated_at': datetime.utcnow().replace(microsecond=0).isoformat() + 'Z',
        'count': len(items),
        'bands': meeting_rooms_health_bands(rows),
        'buckets': by_bucket,
        'headline': meeting_rooms_headline(rows),
        'items': items[:40],
    }


def meeting_rooms_headline(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return 'Meeting Rooms has no rows in the local ledger yet.'
    bands = meeting_rooms_health_bands(rows)
    critical = bands.get('critical', 0)
    if critical:
        return f'Meeting Rooms: {critical} critical records need a named owner this shift.'
    return f'Meeting Rooms: {len(rows)} records are inside the operating range.'


def meeting_rooms_csv_lines(rows: list[dict[str, Any]]) -> list[str]:
    header = ['id', 'title', 'status', 'days', 'bucket', 'band', 'owner', 'health_score']
    lines = [','.join(header)]
    for row in rows:
        item = meeting_rooms_line_item(row)
        lines.append(','.join(str(item.get(col, '')).replace(',', ' ') for col in header))
    return lines


def meeting_rooms_status_share(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped = meeting_rooms_group_status(rows)
    total = max(1, len(rows))
    share = []
    for status in ['open', 'held', 'offline']:
        count = len(grouped.get(status, []))
        share.append({'status': status, 'count': count, 'pct': int((count / total) * 100)})
    return share


def meeting_rooms_owner_load(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    load: dict[str, int] = {}
    for row in rows:
        owner = meeting_rooms_owner_hint(row)
        load[owner] = load.get(owner, 0) + 1
    ranked = sorted(load.items(), key=lambda pair: pair[1], reverse=True)
    return [{'owner': name, 'count': count} for name, count in ranked]


def meeting_rooms_weekly_story(rows: list[dict[str, Any]]) -> list[str]:
    story = []
    briefing = meeting_rooms_briefing(rows)
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
    story.append('Meeting Rooms briefing is local-only and does not call an external network.')
    return story


def meeting_rooms_print_pack(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'briefing': meeting_rooms_briefing(rows),
        'share': meeting_rooms_status_share(rows),
        'owners': meeting_rooms_owner_load(rows),
        'story': meeting_rooms_weekly_story(rows),
    }


class MeetingRoomsReporter:
    """Builds operator-facing packs for Meeting Rooms."""

    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.rows = list(rows or [])

    def refresh(self, rows: list[dict[str, Any]]) -> None:
        self.rows = list(rows)

    def briefing(self) -> dict[str, Any]:
        return meeting_rooms_briefing(self.rows)

    def story(self) -> list[str]:
        return meeting_rooms_weekly_story(self.rows)

    def csv(self) -> str:
        return '\n'.join(meeting_rooms_csv_lines(self.rows)) + '\n'

    def pack(self) -> dict[str, Any]:
        return meeting_rooms_print_pack(self.rows)


def build_meeting_rooms_reporter(rows: list[dict[str, Any]]) -> MeetingRoomsReporter:
    return MeetingRoomsReporter(rows)

def meeting_rooms_report_by_room_code(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Meeting Rooms by Room Code."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('room_code') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'room_code'} for label, count in ranked]


def meeting_rooms_report_by_floor(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Meeting Rooms by Floor."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('floor') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'floor'} for label, count in ranked]


def meeting_rooms_report_by_capacity(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Meeting Rooms by Capacity."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('capacity') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'capacity'} for label, count in ranked]


def meeting_rooms_outlier_capacity(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
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


def meeting_rooms_report_by_equipment(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Meeting Rooms by Equipment."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('equipment') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'equipment'} for label, count in ranked]


def meeting_rooms_report_by_status(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Meeting Rooms by Status."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('status') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'status'} for label, count in ranked]


