"""Period reports and operator briefings for Travel Bookings."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.domains.travel_bookings.queries import travel_bookings_group_status, travel_bookings_health_bands, travel_bookings_completeness
from app.domains.travel_bookings.policies import travel_bookings_risk_band, travel_bookings_sla_hours, travel_bookings_owner_hint

DOMAIN_TITLE = 'Travel Bookings'


def travel_bookings_age_days(row: dict[str, Any]) -> int:
    created = str(row.get('created_at') or '')
    try:
        parsed = datetime.fromisoformat(created.replace('Z', ''))
    except ValueError:
        return 0
    return max(0, (datetime.utcnow() - parsed).days)


def travel_bookings_bucket(days: int) -> str:
    if days < 3:
        return 'fresh'
    if days < 14:
        return 'current'
    if days < 45:
        return 'aging'
    return 'legacy'


def travel_bookings_line_item(row: dict[str, Any]) -> dict[str, Any]:
    days = travel_bookings_age_days(row)
    return {
        'id': row.get('id'),
        'title': row.get('booking_no'),
        'status': row.get('status'),
        'days': days,
        'bucket': travel_bookings_bucket(days),
        'band': travel_bookings_risk_band(row),
        'owner': travel_bookings_owner_hint(row),
        'sla_hours': travel_bookings_sla_hours(row),
        'completeness': travel_bookings_completeness(row),
        'health_score': row.get('health_score'),
    }


def travel_bookings_briefing(rows: list[dict[str, Any]]) -> dict[str, Any]:
    items = [travel_bookings_line_item(row) for row in rows]
    by_bucket = {'fresh': 0, 'current': 0, 'aging': 0, 'legacy': 0}
    for item in items:
        by_bucket[str(item['bucket'])] += 1
    return {
        'title': DOMAIN_TITLE,
        'generated_at': datetime.utcnow().replace(microsecond=0).isoformat() + 'Z',
        'count': len(items),
        'bands': travel_bookings_health_bands(rows),
        'buckets': by_bucket,
        'headline': travel_bookings_headline(rows),
        'items': items[:40],
    }


def travel_bookings_headline(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return 'Travel Bookings has no rows in the local ledger yet.'
    bands = travel_bookings_health_bands(rows)
    critical = bands.get('critical', 0)
    if critical:
        return f'Travel Bookings: {critical} critical records need a named owner this shift.'
    return f'Travel Bookings: {len(rows)} records are inside the operating range.'


def travel_bookings_csv_lines(rows: list[dict[str, Any]]) -> list[str]:
    header = ['id', 'title', 'status', 'days', 'bucket', 'band', 'owner', 'health_score']
    lines = [','.join(header)]
    for row in rows:
        item = travel_bookings_line_item(row)
        lines.append(','.join(str(item.get(col, '')).replace(',', ' ') for col in header))
    return lines


def travel_bookings_status_share(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped = travel_bookings_group_status(rows)
    total = max(1, len(rows))
    share = []
    for status in ['held', 'ticketed', 'in_trip', 'complete', 'void']:
        count = len(grouped.get(status, []))
        share.append({'status': status, 'count': count, 'pct': int((count / total) * 100)})
    return share


def travel_bookings_owner_load(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    load: dict[str, int] = {}
    for row in rows:
        owner = travel_bookings_owner_hint(row)
        load[owner] = load.get(owner, 0) + 1
    ranked = sorted(load.items(), key=lambda pair: pair[1], reverse=True)
    return [{'owner': name, 'count': count} for name, count in ranked]


def travel_bookings_weekly_story(rows: list[dict[str, Any]]) -> list[str]:
    story = []
    briefing = travel_bookings_briefing(rows)
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
    story.append('Travel Bookings briefing is local-only and does not call an external network.')
    return story


def travel_bookings_print_pack(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'briefing': travel_bookings_briefing(rows),
        'share': travel_bookings_status_share(rows),
        'owners': travel_bookings_owner_load(rows),
        'story': travel_bookings_weekly_story(rows),
    }


class TravelBookingsReporter:
    """Builds operator-facing packs for Travel Bookings."""

    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.rows = list(rows or [])

    def refresh(self, rows: list[dict[str, Any]]) -> None:
        self.rows = list(rows)

    def briefing(self) -> dict[str, Any]:
        return travel_bookings_briefing(self.rows)

    def story(self) -> list[str]:
        return travel_bookings_weekly_story(self.rows)

    def csv(self) -> str:
        return '\n'.join(travel_bookings_csv_lines(self.rows)) + '\n'

    def pack(self) -> dict[str, Any]:
        return travel_bookings_print_pack(self.rows)


def build_travel_bookings_reporter(rows: list[dict[str, Any]]) -> TravelBookingsReporter:
    return TravelBookingsReporter(rows)

def travel_bookings_report_by_booking_no(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Travel Bookings by Booking No."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('booking_no') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'booking_no'} for label, count in ranked]


def travel_bookings_report_by_traveler(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Travel Bookings by Traveler."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('traveler') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'traveler'} for label, count in ranked]


def travel_bookings_report_by_origin(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Travel Bookings by Origin."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('origin') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'origin'} for label, count in ranked]


def travel_bookings_report_by_destination(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Travel Bookings by Destination."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('destination') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'destination'} for label, count in ranked]


def travel_bookings_report_by_departs_on(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Travel Bookings by Departs On."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('departs_on') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'departs_on'} for label, count in ranked]


def travel_bookings_report_by_status(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Travel Bookings by Status."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('status') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'status'} for label, count in ranked]


