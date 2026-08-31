"""Period reports and operator briefings for Campaign Studio."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.domains.campaigns.queries import campaigns_group_status, campaigns_health_bands, campaigns_completeness
from app.domains.campaigns.policies import campaigns_risk_band, campaigns_sla_hours, campaigns_owner_hint

DOMAIN_TITLE = 'Campaign Studio'


def campaigns_age_days(row: dict[str, Any]) -> int:
    created = str(row.get('created_at') or '')
    try:
        parsed = datetime.fromisoformat(created.replace('Z', ''))
    except ValueError:
        return 0
    return max(0, (datetime.utcnow() - parsed).days)


def campaigns_bucket(days: int) -> str:
    if days < 3:
        return 'fresh'
    if days < 14:
        return 'current'
    if days < 45:
        return 'aging'
    return 'legacy'


def campaigns_line_item(row: dict[str, Any]) -> dict[str, Any]:
    days = campaigns_age_days(row)
    return {
        'id': row.get('id'),
        'title': row.get('campaign_name'),
        'status': row.get('status'),
        'days': days,
        'bucket': campaigns_bucket(days),
        'band': campaigns_risk_band(row),
        'owner': campaigns_owner_hint(row),
        'sla_hours': campaigns_sla_hours(row),
        'completeness': campaigns_completeness(row),
        'health_score': row.get('health_score'),
    }


def campaigns_briefing(rows: list[dict[str, Any]]) -> dict[str, Any]:
    items = [campaigns_line_item(row) for row in rows]
    by_bucket = {'fresh': 0, 'current': 0, 'aging': 0, 'legacy': 0}
    for item in items:
        by_bucket[str(item['bucket'])] += 1
    return {
        'title': DOMAIN_TITLE,
        'generated_at': datetime.utcnow().replace(microsecond=0).isoformat() + 'Z',
        'count': len(items),
        'bands': campaigns_health_bands(rows),
        'buckets': by_bucket,
        'headline': campaigns_headline(rows),
        'items': items[:40],
    }


def campaigns_headline(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return 'Campaign Studio has no rows in the local ledger yet.'
    bands = campaigns_health_bands(rows)
    critical = bands.get('critical', 0)
    if critical:
        return f'Campaign Studio: {critical} critical records need a named owner this shift.'
    return f'Campaign Studio: {len(rows)} records are inside the operating range.'


def campaigns_csv_lines(rows: list[dict[str, Any]]) -> list[str]:
    header = ['id', 'title', 'status', 'days', 'bucket', 'band', 'owner', 'health_score']
    lines = [','.join(header)]
    for row in rows:
        item = campaigns_line_item(row)
        lines.append(','.join(str(item.get(col, '')).replace(',', ' ') for col in header))
    return lines


def campaigns_status_share(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped = campaigns_group_status(rows)
    total = max(1, len(rows))
    share = []
    for status in ['planned', 'live', 'paused', 'complete']:
        count = len(grouped.get(status, []))
        share.append({'status': status, 'count': count, 'pct': int((count / total) * 100)})
    return share


def campaigns_owner_load(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    load: dict[str, int] = {}
    for row in rows:
        owner = campaigns_owner_hint(row)
        load[owner] = load.get(owner, 0) + 1
    ranked = sorted(load.items(), key=lambda pair: pair[1], reverse=True)
    return [{'owner': name, 'count': count} for name, count in ranked]


def campaigns_weekly_story(rows: list[dict[str, Any]]) -> list[str]:
    story = []
    briefing = campaigns_briefing(rows)
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
    story.append('Campaign Studio briefing is local-only and does not call an external network.')
    return story


def campaigns_print_pack(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'briefing': campaigns_briefing(rows),
        'share': campaigns_status_share(rows),
        'owners': campaigns_owner_load(rows),
        'story': campaigns_weekly_story(rows),
    }


class CampaignsReporter:
    """Builds operator-facing packs for Campaign Studio."""

    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.rows = list(rows or [])

    def refresh(self, rows: list[dict[str, Any]]) -> None:
        self.rows = list(rows)

    def briefing(self) -> dict[str, Any]:
        return campaigns_briefing(self.rows)

    def story(self) -> list[str]:
        return campaigns_weekly_story(self.rows)

    def csv(self) -> str:
        return '\n'.join(campaigns_csv_lines(self.rows)) + '\n'

    def pack(self) -> dict[str, Any]:
        return campaigns_print_pack(self.rows)


def build_campaigns_reporter(rows: list[dict[str, Any]]) -> CampaignsReporter:
    return CampaignsReporter(rows)

def campaigns_report_by_campaign_name(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Campaign Studio by Campaign Name."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('campaign_name') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'campaign_name'} for label, count in ranked]


def campaigns_report_by_channel(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Campaign Studio by Channel."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('channel') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'channel'} for label, count in ranked]


def campaigns_report_by_budget_cents(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Campaign Studio by Budget Cents."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('budget_cents') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'budget_cents'} for label, count in ranked]


def campaigns_outlier_budget_cents(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    values = []
    for row in rows:
        try:
            values.append(int(row.get('budget_cents') or 0))
        except (TypeError, ValueError):
            values.append(0)
    if not values:
        return []
    avg = sum(values) / len(values)
    flagged = []
    for row, value in zip(rows, values):
        if value > avg * 3 and value > 0:
            flagged.append({'id': row.get('id'), 'field': 'budget_cents', 'value': value, 'avg': int(avg)})
    return flagged


def campaigns_report_by_starts_on(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Campaign Studio by Starts On."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('starts_on') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'starts_on'} for label, count in ranked]


def campaigns_report_by_ends_on(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Campaign Studio by Ends On."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('ends_on') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'ends_on'} for label, count in ranked]


def campaigns_report_by_status(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Campaign Studio by Status."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('status') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'status'} for label, count in ranked]


