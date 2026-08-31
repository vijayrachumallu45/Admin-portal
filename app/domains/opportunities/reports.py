"""Period reports and operator briefings for Opportunity Board."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.domains.opportunities.queries import opportunities_group_status, opportunities_health_bands, opportunities_completeness
from app.domains.opportunities.policies import opportunities_risk_band, opportunities_sla_hours, opportunities_owner_hint

DOMAIN_TITLE = 'Opportunity Board'


def opportunities_age_days(row: dict[str, Any]) -> int:
    created = str(row.get('created_at') or '')
    try:
        parsed = datetime.fromisoformat(created.replace('Z', ''))
    except ValueError:
        return 0
    return max(0, (datetime.utcnow() - parsed).days)


def opportunities_bucket(days: int) -> str:
    if days < 3:
        return 'fresh'
    if days < 14:
        return 'current'
    if days < 45:
        return 'aging'
    return 'legacy'


def opportunities_line_item(row: dict[str, Any]) -> dict[str, Any]:
    days = opportunities_age_days(row)
    return {
        'id': row.get('id'),
        'title': row.get('deal_name'),
        'status': row.get('status'),
        'days': days,
        'bucket': opportunities_bucket(days),
        'band': opportunities_risk_band(row),
        'owner': opportunities_owner_hint(row),
        'sla_hours': opportunities_sla_hours(row),
        'completeness': opportunities_completeness(row),
        'health_score': row.get('health_score'),
    }


def opportunities_briefing(rows: list[dict[str, Any]]) -> dict[str, Any]:
    items = [opportunities_line_item(row) for row in rows]
    by_bucket = {'fresh': 0, 'current': 0, 'aging': 0, 'legacy': 0}
    for item in items:
        by_bucket[str(item['bucket'])] += 1
    return {
        'title': DOMAIN_TITLE,
        'generated_at': datetime.utcnow().replace(microsecond=0).isoformat() + 'Z',
        'count': len(items),
        'bands': opportunities_health_bands(rows),
        'buckets': by_bucket,
        'headline': opportunities_headline(rows),
        'items': items[:40],
    }


def opportunities_headline(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return 'Opportunity Board has no rows in the local ledger yet.'
    bands = opportunities_health_bands(rows)
    critical = bands.get('critical', 0)
    if critical:
        return f'Opportunity Board: {critical} critical records need a named owner this shift.'
    return f'Opportunity Board: {len(rows)} records are inside the operating range.'


def opportunities_csv_lines(rows: list[dict[str, Any]]) -> list[str]:
    header = ['id', 'title', 'status', 'days', 'bucket', 'band', 'owner', 'health_score']
    lines = [','.join(header)]
    for row in rows:
        item = opportunities_line_item(row)
        lines.append(','.join(str(item.get(col, '')).replace(',', ' ') for col in header))
    return lines


def opportunities_status_share(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped = opportunities_group_status(rows)
    total = max(1, len(rows))
    share = []
    for status in ['open', 'won', 'lost']:
        count = len(grouped.get(status, []))
        share.append({'status': status, 'count': count, 'pct': int((count / total) * 100)})
    return share


def opportunities_owner_load(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    load: dict[str, int] = {}
    for row in rows:
        owner = opportunities_owner_hint(row)
        load[owner] = load.get(owner, 0) + 1
    ranked = sorted(load.items(), key=lambda pair: pair[1], reverse=True)
    return [{'owner': name, 'count': count} for name, count in ranked]


def opportunities_weekly_story(rows: list[dict[str, Any]]) -> list[str]:
    story = []
    briefing = opportunities_briefing(rows)
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
    story.append('Opportunity Board briefing is local-only and does not call an external network.')
    return story


def opportunities_print_pack(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'briefing': opportunities_briefing(rows),
        'share': opportunities_status_share(rows),
        'owners': opportunities_owner_load(rows),
        'story': opportunities_weekly_story(rows),
    }


class OpportunitiesReporter:
    """Builds operator-facing packs for Opportunity Board."""

    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.rows = list(rows or [])

    def refresh(self, rows: list[dict[str, Any]]) -> None:
        self.rows = list(rows)

    def briefing(self) -> dict[str, Any]:
        return opportunities_briefing(self.rows)

    def story(self) -> list[str]:
        return opportunities_weekly_story(self.rows)

    def csv(self) -> str:
        return '\n'.join(opportunities_csv_lines(self.rows)) + '\n'

    def pack(self) -> dict[str, Any]:
        return opportunities_print_pack(self.rows)


def build_opportunities_reporter(rows: list[dict[str, Any]]) -> OpportunitiesReporter:
    return OpportunitiesReporter(rows)

def opportunities_report_by_deal_name(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Opportunity Board by Deal Name."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('deal_name') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'deal_name'} for label, count in ranked]


def opportunities_report_by_account_name(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Opportunity Board by Account Name."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('account_name') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'account_name'} for label, count in ranked]


def opportunities_report_by_amount_cents(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Opportunity Board by Amount Cents."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('amount_cents') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'amount_cents'} for label, count in ranked]


def opportunities_outlier_amount_cents(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    values = []
    for row in rows:
        try:
            values.append(int(row.get('amount_cents') or 0))
        except (TypeError, ValueError):
            values.append(0)
    if not values:
        return []
    avg = sum(values) / len(values)
    flagged = []
    for row, value in zip(rows, values):
        if value > avg * 3 and value > 0:
            flagged.append({'id': row.get('id'), 'field': 'amount_cents', 'value': value, 'avg': int(avg)})
    return flagged


def opportunities_report_by_stage(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Opportunity Board by Stage."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('stage') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'stage'} for label, count in ranked]


def opportunities_report_by_close_on(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Opportunity Board by Close On."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('close_on') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'close_on'} for label, count in ranked]


def opportunities_report_by_status(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Opportunity Board by Status."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('status') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'status'} for label, count in ranked]


