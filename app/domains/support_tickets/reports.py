"""Period reports and operator briefings for Support Queue."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.domains.support_tickets.queries import support_tickets_group_status, support_tickets_health_bands, support_tickets_completeness
from app.domains.support_tickets.policies import support_tickets_risk_band, support_tickets_sla_hours, support_tickets_owner_hint

DOMAIN_TITLE = 'Support Queue'


def support_tickets_age_days(row: dict[str, Any]) -> int:
    created = str(row.get('created_at') or '')
    try:
        parsed = datetime.fromisoformat(created.replace('Z', ''))
    except ValueError:
        return 0
    return max(0, (datetime.utcnow() - parsed).days)


def support_tickets_bucket(days: int) -> str:
    if days < 3:
        return 'fresh'
    if days < 14:
        return 'current'
    if days < 45:
        return 'aging'
    return 'legacy'


def support_tickets_line_item(row: dict[str, Any]) -> dict[str, Any]:
    days = support_tickets_age_days(row)
    return {
        'id': row.get('id'),
        'title': row.get('ticket_no'),
        'status': row.get('status'),
        'days': days,
        'bucket': support_tickets_bucket(days),
        'band': support_tickets_risk_band(row),
        'owner': support_tickets_owner_hint(row),
        'sla_hours': support_tickets_sla_hours(row),
        'completeness': support_tickets_completeness(row),
        'health_score': row.get('health_score'),
    }


def support_tickets_briefing(rows: list[dict[str, Any]]) -> dict[str, Any]:
    items = [support_tickets_line_item(row) for row in rows]
    by_bucket = {'fresh': 0, 'current': 0, 'aging': 0, 'legacy': 0}
    for item in items:
        by_bucket[str(item['bucket'])] += 1
    return {
        'title': DOMAIN_TITLE,
        'generated_at': datetime.utcnow().replace(microsecond=0).isoformat() + 'Z',
        'count': len(items),
        'bands': support_tickets_health_bands(rows),
        'buckets': by_bucket,
        'headline': support_tickets_headline(rows),
        'items': items[:40],
    }


def support_tickets_headline(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return 'Support Queue has no rows in the local ledger yet.'
    bands = support_tickets_health_bands(rows)
    critical = bands.get('critical', 0)
    if critical:
        return f'Support Queue: {critical} critical records need a named owner this shift.'
    return f'Support Queue: {len(rows)} records are inside the operating range.'


def support_tickets_csv_lines(rows: list[dict[str, Any]]) -> list[str]:
    header = ['id', 'title', 'status', 'days', 'bucket', 'band', 'owner', 'health_score']
    lines = [','.join(header)]
    for row in rows:
        item = support_tickets_line_item(row)
        lines.append(','.join(str(item.get(col, '')).replace(',', ' ') for col in header))
    return lines


def support_tickets_status_share(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped = support_tickets_group_status(rows)
    total = max(1, len(rows))
    share = []
    for status in ['new', 'open', 'pending', 'resolved', 'closed']:
        count = len(grouped.get(status, []))
        share.append({'status': status, 'count': count, 'pct': int((count / total) * 100)})
    return share


def support_tickets_owner_load(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    load: dict[str, int] = {}
    for row in rows:
        owner = support_tickets_owner_hint(row)
        load[owner] = load.get(owner, 0) + 1
    ranked = sorted(load.items(), key=lambda pair: pair[1], reverse=True)
    return [{'owner': name, 'count': count} for name, count in ranked]


def support_tickets_weekly_story(rows: list[dict[str, Any]]) -> list[str]:
    story = []
    briefing = support_tickets_briefing(rows)
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
    story.append('Support Queue briefing is local-only and does not call an external network.')
    return story


def support_tickets_print_pack(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'briefing': support_tickets_briefing(rows),
        'share': support_tickets_status_share(rows),
        'owners': support_tickets_owner_load(rows),
        'story': support_tickets_weekly_story(rows),
    }


class SupportTicketsReporter:
    """Builds operator-facing packs for Support Queue."""

    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.rows = list(rows or [])

    def refresh(self, rows: list[dict[str, Any]]) -> None:
        self.rows = list(rows)

    def briefing(self) -> dict[str, Any]:
        return support_tickets_briefing(self.rows)

    def story(self) -> list[str]:
        return support_tickets_weekly_story(self.rows)

    def csv(self) -> str:
        return '\n'.join(support_tickets_csv_lines(self.rows)) + '\n'

    def pack(self) -> dict[str, Any]:
        return support_tickets_print_pack(self.rows)


def build_support_tickets_reporter(rows: list[dict[str, Any]]) -> SupportTicketsReporter:
    return SupportTicketsReporter(rows)

def support_tickets_report_by_ticket_no(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Support Queue by Ticket No."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('ticket_no') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'ticket_no'} for label, count in ranked]


def support_tickets_report_by_subject(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Support Queue by Subject."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('subject') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'subject'} for label, count in ranked]


def support_tickets_report_by_severity(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Support Queue by Severity."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('severity') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'severity'} for label, count in ranked]


def support_tickets_report_by_requester(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Support Queue by Requester."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('requester') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'requester'} for label, count in ranked]


def support_tickets_report_by_assignee(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Support Queue by Assignee."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('assignee') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'assignee'} for label, count in ranked]


def support_tickets_report_by_status(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Support Queue by Status."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('status') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'status'} for label, count in ranked]


