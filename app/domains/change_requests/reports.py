"""Period reports and operator briefings for Change Requests."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.domains.change_requests.queries import change_requests_group_status, change_requests_health_bands, change_requests_completeness
from app.domains.change_requests.policies import change_requests_risk_band, change_requests_sla_hours, change_requests_owner_hint

DOMAIN_TITLE = 'Change Requests'


def change_requests_age_days(row: dict[str, Any]) -> int:
    created = str(row.get('created_at') or '')
    try:
        parsed = datetime.fromisoformat(created.replace('Z', ''))
    except ValueError:
        return 0
    return max(0, (datetime.utcnow() - parsed).days)


def change_requests_bucket(days: int) -> str:
    if days < 3:
        return 'fresh'
    if days < 14:
        return 'current'
    if days < 45:
        return 'aging'
    return 'legacy'


def change_requests_line_item(row: dict[str, Any]) -> dict[str, Any]:
    days = change_requests_age_days(row)
    return {
        'id': row.get('id'),
        'title': row.get('change_no'),
        'status': row.get('status'),
        'days': days,
        'bucket': change_requests_bucket(days),
        'band': change_requests_risk_band(row),
        'owner': change_requests_owner_hint(row),
        'sla_hours': change_requests_sla_hours(row),
        'completeness': change_requests_completeness(row),
        'health_score': row.get('health_score'),
    }


def change_requests_briefing(rows: list[dict[str, Any]]) -> dict[str, Any]:
    items = [change_requests_line_item(row) for row in rows]
    by_bucket = {'fresh': 0, 'current': 0, 'aging': 0, 'legacy': 0}
    for item in items:
        by_bucket[str(item['bucket'])] += 1
    return {
        'title': DOMAIN_TITLE,
        'generated_at': datetime.utcnow().replace(microsecond=0).isoformat() + 'Z',
        'count': len(items),
        'bands': change_requests_health_bands(rows),
        'buckets': by_bucket,
        'headline': change_requests_headline(rows),
        'items': items[:40],
    }


def change_requests_headline(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return 'Change Requests has no rows in the local ledger yet.'
    bands = change_requests_health_bands(rows)
    critical = bands.get('critical', 0)
    if critical:
        return f'Change Requests: {critical} critical records need a named owner this shift.'
    return f'Change Requests: {len(rows)} records are inside the operating range.'


def change_requests_csv_lines(rows: list[dict[str, Any]]) -> list[str]:
    header = ['id', 'title', 'status', 'days', 'bucket', 'band', 'owner', 'health_score']
    lines = [','.join(header)]
    for row in rows:
        item = change_requests_line_item(row)
        lines.append(','.join(str(item.get(col, '')).replace(',', ' ') for col in header))
    return lines


def change_requests_status_share(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped = change_requests_group_status(rows)
    total = max(1, len(rows))
    share = []
    for status in ['draft', 'cab', 'approved', 'executed', 'failed']:
        count = len(grouped.get(status, []))
        share.append({'status': status, 'count': count, 'pct': int((count / total) * 100)})
    return share


def change_requests_owner_load(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    load: dict[str, int] = {}
    for row in rows:
        owner = change_requests_owner_hint(row)
        load[owner] = load.get(owner, 0) + 1
    ranked = sorted(load.items(), key=lambda pair: pair[1], reverse=True)
    return [{'owner': name, 'count': count} for name, count in ranked]


def change_requests_weekly_story(rows: list[dict[str, Any]]) -> list[str]:
    story = []
    briefing = change_requests_briefing(rows)
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
    story.append('Change Requests briefing is local-only and does not call an external network.')
    return story


def change_requests_print_pack(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'briefing': change_requests_briefing(rows),
        'share': change_requests_status_share(rows),
        'owners': change_requests_owner_load(rows),
        'story': change_requests_weekly_story(rows),
    }


class ChangeRequestsReporter:
    """Builds operator-facing packs for Change Requests."""

    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.rows = list(rows or [])

    def refresh(self, rows: list[dict[str, Any]]) -> None:
        self.rows = list(rows)

    def briefing(self) -> dict[str, Any]:
        return change_requests_briefing(self.rows)

    def story(self) -> list[str]:
        return change_requests_weekly_story(self.rows)

    def csv(self) -> str:
        return '\n'.join(change_requests_csv_lines(self.rows)) + '\n'

    def pack(self) -> dict[str, Any]:
        return change_requests_print_pack(self.rows)


def build_change_requests_reporter(rows: list[dict[str, Any]]) -> ChangeRequestsReporter:
    return ChangeRequestsReporter(rows)

def change_requests_report_by_change_no(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Change Requests by Change No."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('change_no') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'change_no'} for label, count in ranked]


def change_requests_report_by_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Change Requests by Summary."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('summary') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'summary'} for label, count in ranked]


def change_requests_report_by_risk(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Change Requests by Risk."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('risk') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'risk'} for label, count in ranked]


def change_requests_report_by_window_start(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Change Requests by Window Start."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('window_start') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'window_start'} for label, count in ranked]


def change_requests_report_by_owner(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Change Requests by Owner."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('owner') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'owner'} for label, count in ranked]


def change_requests_report_by_status(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Change Requests by Status."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('status') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'status'} for label, count in ranked]


