"""Period reports and operator briefings for IT Asset Register."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.domains.it_assets.queries import it_assets_group_status, it_assets_health_bands, it_assets_completeness
from app.domains.it_assets.policies import it_assets_risk_band, it_assets_sla_hours, it_assets_owner_hint

DOMAIN_TITLE = 'IT Asset Register'


def it_assets_age_days(row: dict[str, Any]) -> int:
    created = str(row.get('created_at') or '')
    try:
        parsed = datetime.fromisoformat(created.replace('Z', ''))
    except ValueError:
        return 0
    return max(0, (datetime.utcnow() - parsed).days)


def it_assets_bucket(days: int) -> str:
    if days < 3:
        return 'fresh'
    if days < 14:
        return 'current'
    if days < 45:
        return 'aging'
    return 'legacy'


def it_assets_line_item(row: dict[str, Any]) -> dict[str, Any]:
    days = it_assets_age_days(row)
    return {
        'id': row.get('id'),
        'title': row.get('asset_tag'),
        'status': row.get('status'),
        'days': days,
        'bucket': it_assets_bucket(days),
        'band': it_assets_risk_band(row),
        'owner': it_assets_owner_hint(row),
        'sla_hours': it_assets_sla_hours(row),
        'completeness': it_assets_completeness(row),
        'health_score': row.get('health_score'),
    }


def it_assets_briefing(rows: list[dict[str, Any]]) -> dict[str, Any]:
    items = [it_assets_line_item(row) for row in rows]
    by_bucket = {'fresh': 0, 'current': 0, 'aging': 0, 'legacy': 0}
    for item in items:
        by_bucket[str(item['bucket'])] += 1
    return {
        'title': DOMAIN_TITLE,
        'generated_at': datetime.utcnow().replace(microsecond=0).isoformat() + 'Z',
        'count': len(items),
        'bands': it_assets_health_bands(rows),
        'buckets': by_bucket,
        'headline': it_assets_headline(rows),
        'items': items[:40],
    }


def it_assets_headline(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return 'IT Asset Register has no rows in the local ledger yet.'
    bands = it_assets_health_bands(rows)
    critical = bands.get('critical', 0)
    if critical:
        return f'IT Asset Register: {critical} critical records need a named owner this shift.'
    return f'IT Asset Register: {len(rows)} records are inside the operating range.'


def it_assets_csv_lines(rows: list[dict[str, Any]]) -> list[str]:
    header = ['id', 'title', 'status', 'days', 'bucket', 'band', 'owner', 'health_score']
    lines = [','.join(header)]
    for row in rows:
        item = it_assets_line_item(row)
        lines.append(','.join(str(item.get(col, '')).replace(',', ' ') for col in header))
    return lines


def it_assets_status_share(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped = it_assets_group_status(rows)
    total = max(1, len(rows))
    share = []
    for status in ['stock', 'assigned', 'repair', 'retired']:
        count = len(grouped.get(status, []))
        share.append({'status': status, 'count': count, 'pct': int((count / total) * 100)})
    return share


def it_assets_owner_load(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    load: dict[str, int] = {}
    for row in rows:
        owner = it_assets_owner_hint(row)
        load[owner] = load.get(owner, 0) + 1
    ranked = sorted(load.items(), key=lambda pair: pair[1], reverse=True)
    return [{'owner': name, 'count': count} for name, count in ranked]


def it_assets_weekly_story(rows: list[dict[str, Any]]) -> list[str]:
    story = []
    briefing = it_assets_briefing(rows)
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
    story.append('IT Asset Register briefing is local-only and does not call an external network.')
    return story


def it_assets_print_pack(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'briefing': it_assets_briefing(rows),
        'share': it_assets_status_share(rows),
        'owners': it_assets_owner_load(rows),
        'story': it_assets_weekly_story(rows),
    }


class ItAssetsReporter:
    """Builds operator-facing packs for IT Asset Register."""

    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.rows = list(rows or [])

    def refresh(self, rows: list[dict[str, Any]]) -> None:
        self.rows = list(rows)

    def briefing(self) -> dict[str, Any]:
        return it_assets_briefing(self.rows)

    def story(self) -> list[str]:
        return it_assets_weekly_story(self.rows)

    def csv(self) -> str:
        return '\n'.join(it_assets_csv_lines(self.rows)) + '\n'

    def pack(self) -> dict[str, Any]:
        return it_assets_print_pack(self.rows)


def build_it_assets_reporter(rows: list[dict[str, Any]]) -> ItAssetsReporter:
    return ItAssetsReporter(rows)

def it_assets_report_by_asset_tag(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice IT Asset Register by Asset Tag."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('asset_tag') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'asset_tag'} for label, count in ranked]


def it_assets_report_by_model_name(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice IT Asset Register by Model Name."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('model_name') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'model_name'} for label, count in ranked]


def it_assets_report_by_custodian(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice IT Asset Register by Custodian."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('custodian') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'custodian'} for label, count in ranked]


def it_assets_report_by_warranty_on(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice IT Asset Register by Warranty On."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('warranty_on') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'warranty_on'} for label, count in ranked]


def it_assets_report_by_status(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice IT Asset Register by Status."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('status') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'status'} for label, count in ranked]


