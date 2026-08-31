"""Period reports and operator briefings for Access Reviews."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.domains.access_reviews.queries import access_reviews_group_status, access_reviews_health_bands, access_reviews_completeness
from app.domains.access_reviews.policies import access_reviews_risk_band, access_reviews_sla_hours, access_reviews_owner_hint

DOMAIN_TITLE = 'Access Reviews'


def access_reviews_age_days(row: dict[str, Any]) -> int:
    created = str(row.get('created_at') or '')
    try:
        parsed = datetime.fromisoformat(created.replace('Z', ''))
    except ValueError:
        return 0
    return max(0, (datetime.utcnow() - parsed).days)


def access_reviews_bucket(days: int) -> str:
    if days < 3:
        return 'fresh'
    if days < 14:
        return 'current'
    if days < 45:
        return 'aging'
    return 'legacy'


def access_reviews_line_item(row: dict[str, Any]) -> dict[str, Any]:
    days = access_reviews_age_days(row)
    return {
        'id': row.get('id'),
        'title': row.get('campaign'),
        'status': row.get('status'),
        'days': days,
        'bucket': access_reviews_bucket(days),
        'band': access_reviews_risk_band(row),
        'owner': access_reviews_owner_hint(row),
        'sla_hours': access_reviews_sla_hours(row),
        'completeness': access_reviews_completeness(row),
        'health_score': row.get('health_score'),
    }


def access_reviews_briefing(rows: list[dict[str, Any]]) -> dict[str, Any]:
    items = [access_reviews_line_item(row) for row in rows]
    by_bucket = {'fresh': 0, 'current': 0, 'aging': 0, 'legacy': 0}
    for item in items:
        by_bucket[str(item['bucket'])] += 1
    return {
        'title': DOMAIN_TITLE,
        'generated_at': datetime.utcnow().replace(microsecond=0).isoformat() + 'Z',
        'count': len(items),
        'bands': access_reviews_health_bands(rows),
        'buckets': by_bucket,
        'headline': access_reviews_headline(rows),
        'items': items[:40],
    }


def access_reviews_headline(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return 'Access Reviews has no rows in the local ledger yet.'
    bands = access_reviews_health_bands(rows)
    critical = bands.get('critical', 0)
    if critical:
        return f'Access Reviews: {critical} critical records need a named owner this shift.'
    return f'Access Reviews: {len(rows)} records are inside the operating range.'


def access_reviews_csv_lines(rows: list[dict[str, Any]]) -> list[str]:
    header = ['id', 'title', 'status', 'days', 'bucket', 'band', 'owner', 'health_score']
    lines = [','.join(header)]
    for row in rows:
        item = access_reviews_line_item(row)
        lines.append(','.join(str(item.get(col, '')).replace(',', ' ') for col in header))
    return lines


def access_reviews_status_share(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped = access_reviews_group_status(rows)
    total = max(1, len(rows))
    share = []
    for status in ['scheduled', 'in_progress', 'complete', 'overdue']:
        count = len(grouped.get(status, []))
        share.append({'status': status, 'count': count, 'pct': int((count / total) * 100)})
    return share


def access_reviews_owner_load(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    load: dict[str, int] = {}
    for row in rows:
        owner = access_reviews_owner_hint(row)
        load[owner] = load.get(owner, 0) + 1
    ranked = sorted(load.items(), key=lambda pair: pair[1], reverse=True)
    return [{'owner': name, 'count': count} for name, count in ranked]


def access_reviews_weekly_story(rows: list[dict[str, Any]]) -> list[str]:
    story = []
    briefing = access_reviews_briefing(rows)
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
    story.append('Access Reviews briefing is local-only and does not call an external network.')
    return story


def access_reviews_print_pack(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'briefing': access_reviews_briefing(rows),
        'share': access_reviews_status_share(rows),
        'owners': access_reviews_owner_load(rows),
        'story': access_reviews_weekly_story(rows),
    }


class AccessReviewsReporter:
    """Builds operator-facing packs for Access Reviews."""

    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.rows = list(rows or [])

    def refresh(self, rows: list[dict[str, Any]]) -> None:
        self.rows = list(rows)

    def briefing(self) -> dict[str, Any]:
        return access_reviews_briefing(self.rows)

    def story(self) -> list[str]:
        return access_reviews_weekly_story(self.rows)

    def csv(self) -> str:
        return '\n'.join(access_reviews_csv_lines(self.rows)) + '\n'

    def pack(self) -> dict[str, Any]:
        return access_reviews_print_pack(self.rows)


def build_access_reviews_reporter(rows: list[dict[str, Any]]) -> AccessReviewsReporter:
    return AccessReviewsReporter(rows)

def access_reviews_report_by_campaign(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Access Reviews by Campaign."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('campaign') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'campaign'} for label, count in ranked]


def access_reviews_report_by_scope(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Access Reviews by Scope."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('scope') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'scope'} for label, count in ranked]


def access_reviews_report_by_reviewer(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Access Reviews by Reviewer."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('reviewer') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'reviewer'} for label, count in ranked]


def access_reviews_report_by_due_on(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Access Reviews by Due On."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('due_on') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'due_on'} for label, count in ranked]


def access_reviews_report_by_item_count(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Access Reviews by Item Count."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('item_count') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'item_count'} for label, count in ranked]


def access_reviews_outlier_item_count(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    values = []
    for row in rows:
        try:
            values.append(int(row.get('item_count') or 0))
        except (TypeError, ValueError):
            values.append(0)
    if not values:
        return []
    avg = sum(values) / len(values)
    flagged = []
    for row, value in zip(rows, values):
        if value > avg * 3 and value > 0:
            flagged.append({'id': row.get('id'), 'field': 'item_count', 'value': value, 'avg': int(avg)})
    return flagged


def access_reviews_report_by_status(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Access Reviews by Status."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('status') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'status'} for label, count in ranked]


