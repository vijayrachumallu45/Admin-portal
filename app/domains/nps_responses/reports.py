"""Period reports and operator briefings for NPS Responses."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.domains.nps_responses.queries import nps_responses_group_status, nps_responses_health_bands, nps_responses_completeness
from app.domains.nps_responses.policies import nps_responses_risk_band, nps_responses_sla_hours, nps_responses_owner_hint

DOMAIN_TITLE = 'NPS Responses'


def nps_responses_age_days(row: dict[str, Any]) -> int:
    created = str(row.get('created_at') or '')
    try:
        parsed = datetime.fromisoformat(created.replace('Z', ''))
    except ValueError:
        return 0
    return max(0, (datetime.utcnow() - parsed).days)


def nps_responses_bucket(days: int) -> str:
    if days < 3:
        return 'fresh'
    if days < 14:
        return 'current'
    if days < 45:
        return 'aging'
    return 'legacy'


def nps_responses_line_item(row: dict[str, Any]) -> dict[str, Any]:
    days = nps_responses_age_days(row)
    return {
        'id': row.get('id'),
        'title': row.get('account_name'),
        'status': row.get('status'),
        'days': days,
        'bucket': nps_responses_bucket(days),
        'band': nps_responses_risk_band(row),
        'owner': nps_responses_owner_hint(row),
        'sla_hours': nps_responses_sla_hours(row),
        'completeness': nps_responses_completeness(row),
        'health_score': row.get('health_score'),
    }


def nps_responses_briefing(rows: list[dict[str, Any]]) -> dict[str, Any]:
    items = [nps_responses_line_item(row) for row in rows]
    by_bucket = {'fresh': 0, 'current': 0, 'aging': 0, 'legacy': 0}
    for item in items:
        by_bucket[str(item['bucket'])] += 1
    return {
        'title': DOMAIN_TITLE,
        'generated_at': datetime.utcnow().replace(microsecond=0).isoformat() + 'Z',
        'count': len(items),
        'bands': nps_responses_health_bands(rows),
        'buckets': by_bucket,
        'headline': nps_responses_headline(rows),
        'items': items[:40],
    }


def nps_responses_headline(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return 'NPS Responses has no rows in the local ledger yet.'
    bands = nps_responses_health_bands(rows)
    critical = bands.get('critical', 0)
    if critical:
        return f'NPS Responses: {critical} critical records need a named owner this shift.'
    return f'NPS Responses: {len(rows)} records are inside the operating range.'


def nps_responses_csv_lines(rows: list[dict[str, Any]]) -> list[str]:
    header = ['id', 'title', 'status', 'days', 'bucket', 'band', 'owner', 'health_score']
    lines = [','.join(header)]
    for row in rows:
        item = nps_responses_line_item(row)
        lines.append(','.join(str(item.get(col, '')).replace(',', ' ') for col in header))
    return lines


def nps_responses_status_share(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped = nps_responses_group_status(rows)
    total = max(1, len(rows))
    share = []
    for status in ['new', 'follow_up', 'closed']:
        count = len(grouped.get(status, []))
        share.append({'status': status, 'count': count, 'pct': int((count / total) * 100)})
    return share


def nps_responses_owner_load(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    load: dict[str, int] = {}
    for row in rows:
        owner = nps_responses_owner_hint(row)
        load[owner] = load.get(owner, 0) + 1
    ranked = sorted(load.items(), key=lambda pair: pair[1], reverse=True)
    return [{'owner': name, 'count': count} for name, count in ranked]


def nps_responses_weekly_story(rows: list[dict[str, Any]]) -> list[str]:
    story = []
    briefing = nps_responses_briefing(rows)
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
    story.append('NPS Responses briefing is local-only and does not call an external network.')
    return story


def nps_responses_print_pack(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'briefing': nps_responses_briefing(rows),
        'share': nps_responses_status_share(rows),
        'owners': nps_responses_owner_load(rows),
        'story': nps_responses_weekly_story(rows),
    }


class NpsResponsesReporter:
    """Builds operator-facing packs for NPS Responses."""

    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.rows = list(rows or [])

    def refresh(self, rows: list[dict[str, Any]]) -> None:
        self.rows = list(rows)

    def briefing(self) -> dict[str, Any]:
        return nps_responses_briefing(self.rows)

    def story(self) -> list[str]:
        return nps_responses_weekly_story(self.rows)

    def csv(self) -> str:
        return '\n'.join(nps_responses_csv_lines(self.rows)) + '\n'

    def pack(self) -> dict[str, Any]:
        return nps_responses_print_pack(self.rows)


def build_nps_responses_reporter(rows: list[dict[str, Any]]) -> NpsResponsesReporter:
    return NpsResponsesReporter(rows)

def nps_responses_report_by_account_name(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice NPS Responses by Account Name."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('account_name') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'account_name'} for label, count in ranked]


def nps_responses_report_by_score(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice NPS Responses by Score."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('score') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'score'} for label, count in ranked]


def nps_responses_outlier_score(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    values = []
    for row in rows:
        try:
            values.append(int(row.get('score') or 0))
        except (TypeError, ValueError):
            values.append(0)
    if not values:
        return []
    avg = sum(values) / len(values)
    flagged = []
    for row, value in zip(rows, values):
        if value > avg * 3 and value > 0:
            flagged.append({'id': row.get('id'), 'field': 'score', 'value': value, 'avg': int(avg)})
    return flagged


def nps_responses_report_by_comment(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice NPS Responses by Comment."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('comment') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'comment'} for label, count in ranked]


def nps_responses_report_by_owner(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice NPS Responses by Owner."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('owner') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'owner'} for label, count in ranked]


def nps_responses_report_by_status(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice NPS Responses by Status."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('status') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'status'} for label, count in ranked]


