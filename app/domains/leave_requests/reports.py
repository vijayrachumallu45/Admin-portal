"""Period reports and operator briefings for Leave Requests."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.domains.leave_requests.queries import leave_requests_group_status, leave_requests_health_bands, leave_requests_completeness
from app.domains.leave_requests.policies import leave_requests_risk_band, leave_requests_sla_hours, leave_requests_owner_hint

DOMAIN_TITLE = 'Leave Requests'


def leave_requests_age_days(row: dict[str, Any]) -> int:
    created = str(row.get('created_at') or '')
    try:
        parsed = datetime.fromisoformat(created.replace('Z', ''))
    except ValueError:
        return 0
    return max(0, (datetime.utcnow() - parsed).days)


def leave_requests_bucket(days: int) -> str:
    if days < 3:
        return 'fresh'
    if days < 14:
        return 'current'
    if days < 45:
        return 'aging'
    return 'legacy'


def leave_requests_line_item(row: dict[str, Any]) -> dict[str, Any]:
    days = leave_requests_age_days(row)
    return {
        'id': row.get('id'),
        'title': row.get('employee_no'),
        'status': row.get('status'),
        'days': days,
        'bucket': leave_requests_bucket(days),
        'band': leave_requests_risk_band(row),
        'owner': leave_requests_owner_hint(row),
        'sla_hours': leave_requests_sla_hours(row),
        'completeness': leave_requests_completeness(row),
        'health_score': row.get('health_score'),
    }


def leave_requests_briefing(rows: list[dict[str, Any]]) -> dict[str, Any]:
    items = [leave_requests_line_item(row) for row in rows]
    by_bucket = {'fresh': 0, 'current': 0, 'aging': 0, 'legacy': 0}
    for item in items:
        by_bucket[str(item['bucket'])] += 1
    return {
        'title': DOMAIN_TITLE,
        'generated_at': datetime.utcnow().replace(microsecond=0).isoformat() + 'Z',
        'count': len(items),
        'bands': leave_requests_health_bands(rows),
        'buckets': by_bucket,
        'headline': leave_requests_headline(rows),
        'items': items[:40],
    }


def leave_requests_headline(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return 'Leave Requests has no rows in the local ledger yet.'
    bands = leave_requests_health_bands(rows)
    critical = bands.get('critical', 0)
    if critical:
        return f'Leave Requests: {critical} critical records need a named owner this shift.'
    return f'Leave Requests: {len(rows)} records are inside the operating range.'


def leave_requests_csv_lines(rows: list[dict[str, Any]]) -> list[str]:
    header = ['id', 'title', 'status', 'days', 'bucket', 'band', 'owner', 'health_score']
    lines = [','.join(header)]
    for row in rows:
        item = leave_requests_line_item(row)
        lines.append(','.join(str(item.get(col, '')).replace(',', ' ') for col in header))
    return lines


def leave_requests_status_share(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped = leave_requests_group_status(rows)
    total = max(1, len(rows))
    share = []
    for status in ['submitted', 'approved', 'rejected', 'taken']:
        count = len(grouped.get(status, []))
        share.append({'status': status, 'count': count, 'pct': int((count / total) * 100)})
    return share


def leave_requests_owner_load(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    load: dict[str, int] = {}
    for row in rows:
        owner = leave_requests_owner_hint(row)
        load[owner] = load.get(owner, 0) + 1
    ranked = sorted(load.items(), key=lambda pair: pair[1], reverse=True)
    return [{'owner': name, 'count': count} for name, count in ranked]


def leave_requests_weekly_story(rows: list[dict[str, Any]]) -> list[str]:
    story = []
    briefing = leave_requests_briefing(rows)
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
    story.append('Leave Requests briefing is local-only and does not call an external network.')
    return story


def leave_requests_print_pack(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'briefing': leave_requests_briefing(rows),
        'share': leave_requests_status_share(rows),
        'owners': leave_requests_owner_load(rows),
        'story': leave_requests_weekly_story(rows),
    }


class LeaveRequestsReporter:
    """Builds operator-facing packs for Leave Requests."""

    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.rows = list(rows or [])

    def refresh(self, rows: list[dict[str, Any]]) -> None:
        self.rows = list(rows)

    def briefing(self) -> dict[str, Any]:
        return leave_requests_briefing(self.rows)

    def story(self) -> list[str]:
        return leave_requests_weekly_story(self.rows)

    def csv(self) -> str:
        return '\n'.join(leave_requests_csv_lines(self.rows)) + '\n'

    def pack(self) -> dict[str, Any]:
        return leave_requests_print_pack(self.rows)


def build_leave_requests_reporter(rows: list[dict[str, Any]]) -> LeaveRequestsReporter:
    return LeaveRequestsReporter(rows)

def leave_requests_report_by_employee_no(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Leave Requests by Employee No."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('employee_no') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'employee_no'} for label, count in ranked]


def leave_requests_report_by_leave_type(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Leave Requests by Leave Type."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('leave_type') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'leave_type'} for label, count in ranked]


def leave_requests_report_by_starts_on(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Leave Requests by Starts On."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('starts_on') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'starts_on'} for label, count in ranked]


def leave_requests_report_by_ends_on(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Leave Requests by Ends On."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('ends_on') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'ends_on'} for label, count in ranked]


def leave_requests_report_by_days(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Leave Requests by Days."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('days') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'days'} for label, count in ranked]


def leave_requests_outlier_days(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    values = []
    for row in rows:
        try:
            values.append(int(row.get('days') or 0))
        except (TypeError, ValueError):
            values.append(0)
    if not values:
        return []
    avg = sum(values) / len(values)
    flagged = []
    for row, value in zip(rows, values):
        if value > avg * 3 and value > 0:
            flagged.append({'id': row.get('id'), 'field': 'days', 'value': value, 'avg': int(avg)})
    return flagged


def leave_requests_report_by_status(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Leave Requests by Status."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('status') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'status'} for label, count in ranked]


