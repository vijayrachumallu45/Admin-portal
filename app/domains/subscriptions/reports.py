"""Period reports and operator briefings for Subscription Book."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.domains.subscriptions.queries import subscriptions_group_status, subscriptions_health_bands, subscriptions_completeness
from app.domains.subscriptions.policies import subscriptions_risk_band, subscriptions_sla_hours, subscriptions_owner_hint

DOMAIN_TITLE = 'Subscription Book'


def subscriptions_age_days(row: dict[str, Any]) -> int:
    created = str(row.get('created_at') or '')
    try:
        parsed = datetime.fromisoformat(created.replace('Z', ''))
    except ValueError:
        return 0
    return max(0, (datetime.utcnow() - parsed).days)


def subscriptions_bucket(days: int) -> str:
    if days < 3:
        return 'fresh'
    if days < 14:
        return 'current'
    if days < 45:
        return 'aging'
    return 'legacy'


def subscriptions_line_item(row: dict[str, Any]) -> dict[str, Any]:
    days = subscriptions_age_days(row)
    return {
        'id': row.get('id'),
        'title': row.get('account'),
        'status': row.get('status'),
        'days': days,
        'bucket': subscriptions_bucket(days),
        'band': subscriptions_risk_band(row),
        'owner': subscriptions_owner_hint(row),
        'sla_hours': subscriptions_sla_hours(row),
        'completeness': subscriptions_completeness(row),
        'health_score': row.get('health_score'),
    }


def subscriptions_briefing(rows: list[dict[str, Any]]) -> dict[str, Any]:
    items = [subscriptions_line_item(row) for row in rows]
    by_bucket = {'fresh': 0, 'current': 0, 'aging': 0, 'legacy': 0}
    for item in items:
        by_bucket[str(item['bucket'])] += 1
    return {
        'title': DOMAIN_TITLE,
        'generated_at': datetime.utcnow().replace(microsecond=0).isoformat() + 'Z',
        'count': len(items),
        'bands': subscriptions_health_bands(rows),
        'buckets': by_bucket,
        'headline': subscriptions_headline(rows),
        'items': items[:40],
    }


def subscriptions_headline(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return 'Subscription Book has no rows in the local ledger yet.'
    bands = subscriptions_health_bands(rows)
    critical = bands.get('critical', 0)
    if critical:
        return f'Subscription Book: {critical} critical records need a named owner this shift.'
    return f'Subscription Book: {len(rows)} records are inside the operating range.'


def subscriptions_csv_lines(rows: list[dict[str, Any]]) -> list[str]:
    header = ['id', 'title', 'status', 'days', 'bucket', 'band', 'owner', 'health_score']
    lines = [','.join(header)]
    for row in rows:
        item = subscriptions_line_item(row)
        lines.append(','.join(str(item.get(col, '')).replace(',', ' ') for col in header))
    return lines


def subscriptions_status_share(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped = subscriptions_group_status(rows)
    total = max(1, len(rows))
    share = []
    for status in ['trial', 'active', 'past_due', 'cancelled']:
        count = len(grouped.get(status, []))
        share.append({'status': status, 'count': count, 'pct': int((count / total) * 100)})
    return share


def subscriptions_owner_load(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    load: dict[str, int] = {}
    for row in rows:
        owner = subscriptions_owner_hint(row)
        load[owner] = load.get(owner, 0) + 1
    ranked = sorted(load.items(), key=lambda pair: pair[1], reverse=True)
    return [{'owner': name, 'count': count} for name, count in ranked]


def subscriptions_weekly_story(rows: list[dict[str, Any]]) -> list[str]:
    story = []
    briefing = subscriptions_briefing(rows)
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
    story.append('Subscription Book briefing is local-only and does not call an external network.')
    return story


def subscriptions_print_pack(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'briefing': subscriptions_briefing(rows),
        'share': subscriptions_status_share(rows),
        'owners': subscriptions_owner_load(rows),
        'story': subscriptions_weekly_story(rows),
    }


class SubscriptionsReporter:
    """Builds operator-facing packs for Subscription Book."""

    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.rows = list(rows or [])

    def refresh(self, rows: list[dict[str, Any]]) -> None:
        self.rows = list(rows)

    def briefing(self) -> dict[str, Any]:
        return subscriptions_briefing(self.rows)

    def story(self) -> list[str]:
        return subscriptions_weekly_story(self.rows)

    def csv(self) -> str:
        return '\n'.join(subscriptions_csv_lines(self.rows)) + '\n'

    def pack(self) -> dict[str, Any]:
        return subscriptions_print_pack(self.rows)


def build_subscriptions_reporter(rows: list[dict[str, Any]]) -> SubscriptionsReporter:
    return SubscriptionsReporter(rows)

def subscriptions_report_by_account(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Subscription Book by Account."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('account') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'account'} for label, count in ranked]


def subscriptions_report_by_plan_code(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Subscription Book by Plan Code."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('plan_code') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'plan_code'} for label, count in ranked]


def subscriptions_report_by_seats(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Subscription Book by Seats."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('seats') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'seats'} for label, count in ranked]


def subscriptions_outlier_seats(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    values = []
    for row in rows:
        try:
            values.append(int(row.get('seats') or 0))
        except (TypeError, ValueError):
            values.append(0)
    if not values:
        return []
    avg = sum(values) / len(values)
    flagged = []
    for row, value in zip(rows, values):
        if value > avg * 3 and value > 0:
            flagged.append({'id': row.get('id'), 'field': 'seats', 'value': value, 'avg': int(avg)})
    return flagged


def subscriptions_report_by_renew_on(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Subscription Book by Renew On."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('renew_on') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'renew_on'} for label, count in ranked]


def subscriptions_report_by_term_months(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Subscription Book by Term Months."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('term_months') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'term_months'} for label, count in ranked]


def subscriptions_outlier_term_months(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    values = []
    for row in rows:
        try:
            values.append(int(row.get('term_months') or 0))
        except (TypeError, ValueError):
            values.append(0)
    if not values:
        return []
    avg = sum(values) / len(values)
    flagged = []
    for row, value in zip(rows, values):
        if value > avg * 3 and value > 0:
            flagged.append({'id': row.get('id'), 'field': 'term_months', 'value': value, 'avg': int(avg)})
    return flagged


def subscriptions_report_by_arr_cents(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Subscription Book by Arr Cents."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('arr_cents') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'arr_cents'} for label, count in ranked]


def subscriptions_outlier_arr_cents(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    values = []
    for row in rows:
        try:
            values.append(int(row.get('arr_cents') or 0))
        except (TypeError, ValueError):
            values.append(0)
    if not values:
        return []
    avg = sum(values) / len(values)
    flagged = []
    for row, value in zip(rows, values):
        if value > avg * 3 and value > 0:
            flagged.append({'id': row.get('id'), 'field': 'arr_cents', 'value': value, 'avg': int(avg)})
    return flagged


def subscriptions_report_by_status(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Subscription Book by Status."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('status') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'status'} for label, count in ranked]


