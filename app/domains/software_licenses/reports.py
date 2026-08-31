"""Period reports and operator briefings for Software Licenses."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.domains.software_licenses.queries import software_licenses_group_status, software_licenses_health_bands, software_licenses_completeness
from app.domains.software_licenses.policies import software_licenses_risk_band, software_licenses_sla_hours, software_licenses_owner_hint

DOMAIN_TITLE = 'Software Licenses'


def software_licenses_age_days(row: dict[str, Any]) -> int:
    created = str(row.get('created_at') or '')
    try:
        parsed = datetime.fromisoformat(created.replace('Z', ''))
    except ValueError:
        return 0
    return max(0, (datetime.utcnow() - parsed).days)


def software_licenses_bucket(days: int) -> str:
    if days < 3:
        return 'fresh'
    if days < 14:
        return 'current'
    if days < 45:
        return 'aging'
    return 'legacy'


def software_licenses_line_item(row: dict[str, Any]) -> dict[str, Any]:
    days = software_licenses_age_days(row)
    return {
        'id': row.get('id'),
        'title': row.get('product_name'),
        'status': row.get('status'),
        'days': days,
        'bucket': software_licenses_bucket(days),
        'band': software_licenses_risk_band(row),
        'owner': software_licenses_owner_hint(row),
        'sla_hours': software_licenses_sla_hours(row),
        'completeness': software_licenses_completeness(row),
        'health_score': row.get('health_score'),
    }


def software_licenses_briefing(rows: list[dict[str, Any]]) -> dict[str, Any]:
    items = [software_licenses_line_item(row) for row in rows]
    by_bucket = {'fresh': 0, 'current': 0, 'aging': 0, 'legacy': 0}
    for item in items:
        by_bucket[str(item['bucket'])] += 1
    return {
        'title': DOMAIN_TITLE,
        'generated_at': datetime.utcnow().replace(microsecond=0).isoformat() + 'Z',
        'count': len(items),
        'bands': software_licenses_health_bands(rows),
        'buckets': by_bucket,
        'headline': software_licenses_headline(rows),
        'items': items[:40],
    }


def software_licenses_headline(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return 'Software Licenses has no rows in the local ledger yet.'
    bands = software_licenses_health_bands(rows)
    critical = bands.get('critical', 0)
    if critical:
        return f'Software Licenses: {critical} critical records need a named owner this shift.'
    return f'Software Licenses: {len(rows)} records are inside the operating range.'


def software_licenses_csv_lines(rows: list[dict[str, Any]]) -> list[str]:
    header = ['id', 'title', 'status', 'days', 'bucket', 'band', 'owner', 'health_score']
    lines = [','.join(header)]
    for row in rows:
        item = software_licenses_line_item(row)
        lines.append(','.join(str(item.get(col, '')).replace(',', ' ') for col in header))
    return lines


def software_licenses_status_share(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped = software_licenses_group_status(rows)
    total = max(1, len(rows))
    share = []
    for status in ['active', 'unused', 'expiring', 'expired']:
        count = len(grouped.get(status, []))
        share.append({'status': status, 'count': count, 'pct': int((count / total) * 100)})
    return share


def software_licenses_owner_load(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    load: dict[str, int] = {}
    for row in rows:
        owner = software_licenses_owner_hint(row)
        load[owner] = load.get(owner, 0) + 1
    ranked = sorted(load.items(), key=lambda pair: pair[1], reverse=True)
    return [{'owner': name, 'count': count} for name, count in ranked]


def software_licenses_weekly_story(rows: list[dict[str, Any]]) -> list[str]:
    story = []
    briefing = software_licenses_briefing(rows)
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
    story.append('Software Licenses briefing is local-only and does not call an external network.')
    return story


def software_licenses_print_pack(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'briefing': software_licenses_briefing(rows),
        'share': software_licenses_status_share(rows),
        'owners': software_licenses_owner_load(rows),
        'story': software_licenses_weekly_story(rows),
    }


class SoftwareLicensesReporter:
    """Builds operator-facing packs for Software Licenses."""

    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.rows = list(rows or [])

    def refresh(self, rows: list[dict[str, Any]]) -> None:
        self.rows = list(rows)

    def briefing(self) -> dict[str, Any]:
        return software_licenses_briefing(self.rows)

    def story(self) -> list[str]:
        return software_licenses_weekly_story(self.rows)

    def csv(self) -> str:
        return '\n'.join(software_licenses_csv_lines(self.rows)) + '\n'

    def pack(self) -> dict[str, Any]:
        return software_licenses_print_pack(self.rows)


def build_software_licenses_reporter(rows: list[dict[str, Any]]) -> SoftwareLicensesReporter:
    return SoftwareLicensesReporter(rows)

def software_licenses_report_by_product_name(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Software Licenses by Product Name."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('product_name') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'product_name'} for label, count in ranked]


def software_licenses_report_by_publisher(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Software Licenses by Publisher."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('publisher') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'publisher'} for label, count in ranked]


def software_licenses_report_by_seats(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Software Licenses by Seats."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('seats') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'seats'} for label, count in ranked]


def software_licenses_outlier_seats(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
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


def software_licenses_report_by_renew_on(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Software Licenses by Renew On."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('renew_on') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'renew_on'} for label, count in ranked]


def software_licenses_report_by_status(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Software Licenses by Status."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('status') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'status'} for label, count in ranked]


