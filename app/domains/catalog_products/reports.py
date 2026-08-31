"""Period reports and operator briefings for Product Catalog."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.domains.catalog_products.queries import catalog_products_group_status, catalog_products_health_bands, catalog_products_completeness
from app.domains.catalog_products.policies import catalog_products_risk_band, catalog_products_sla_hours, catalog_products_owner_hint

DOMAIN_TITLE = 'Product Catalog'


def catalog_products_age_days(row: dict[str, Any]) -> int:
    created = str(row.get('created_at') or '')
    try:
        parsed = datetime.fromisoformat(created.replace('Z', ''))
    except ValueError:
        return 0
    return max(0, (datetime.utcnow() - parsed).days)


def catalog_products_bucket(days: int) -> str:
    if days < 3:
        return 'fresh'
    if days < 14:
        return 'current'
    if days < 45:
        return 'aging'
    return 'legacy'


def catalog_products_line_item(row: dict[str, Any]) -> dict[str, Any]:
    days = catalog_products_age_days(row)
    return {
        'id': row.get('id'),
        'title': row.get('sku'),
        'status': row.get('status'),
        'days': days,
        'bucket': catalog_products_bucket(days),
        'band': catalog_products_risk_band(row),
        'owner': catalog_products_owner_hint(row),
        'sla_hours': catalog_products_sla_hours(row),
        'completeness': catalog_products_completeness(row),
        'health_score': row.get('health_score'),
    }


def catalog_products_briefing(rows: list[dict[str, Any]]) -> dict[str, Any]:
    items = [catalog_products_line_item(row) for row in rows]
    by_bucket = {'fresh': 0, 'current': 0, 'aging': 0, 'legacy': 0}
    for item in items:
        by_bucket[str(item['bucket'])] += 1
    return {
        'title': DOMAIN_TITLE,
        'generated_at': datetime.utcnow().replace(microsecond=0).isoformat() + 'Z',
        'count': len(items),
        'bands': catalog_products_health_bands(rows),
        'buckets': by_bucket,
        'headline': catalog_products_headline(rows),
        'items': items[:40],
    }


def catalog_products_headline(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return 'Product Catalog has no rows in the local ledger yet.'
    bands = catalog_products_health_bands(rows)
    critical = bands.get('critical', 0)
    if critical:
        return f'Product Catalog: {critical} critical records need a named owner this shift.'
    return f'Product Catalog: {len(rows)} records are inside the operating range.'


def catalog_products_csv_lines(rows: list[dict[str, Any]]) -> list[str]:
    header = ['id', 'title', 'status', 'days', 'bucket', 'band', 'owner', 'health_score']
    lines = [','.join(header)]
    for row in rows:
        item = catalog_products_line_item(row)
        lines.append(','.join(str(item.get(col, '')).replace(',', ' ') for col in header))
    return lines


def catalog_products_status_share(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped = catalog_products_group_status(rows)
    total = max(1, len(rows))
    share = []
    for status in ['draft', 'sellable', 'eol']:
        count = len(grouped.get(status, []))
        share.append({'status': status, 'count': count, 'pct': int((count / total) * 100)})
    return share


def catalog_products_owner_load(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    load: dict[str, int] = {}
    for row in rows:
        owner = catalog_products_owner_hint(row)
        load[owner] = load.get(owner, 0) + 1
    ranked = sorted(load.items(), key=lambda pair: pair[1], reverse=True)
    return [{'owner': name, 'count': count} for name, count in ranked]


def catalog_products_weekly_story(rows: list[dict[str, Any]]) -> list[str]:
    story = []
    briefing = catalog_products_briefing(rows)
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
    story.append('Product Catalog briefing is local-only and does not call an external network.')
    return story


def catalog_products_print_pack(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'briefing': catalog_products_briefing(rows),
        'share': catalog_products_status_share(rows),
        'owners': catalog_products_owner_load(rows),
        'story': catalog_products_weekly_story(rows),
    }


class CatalogProductsReporter:
    """Builds operator-facing packs for Product Catalog."""

    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.rows = list(rows or [])

    def refresh(self, rows: list[dict[str, Any]]) -> None:
        self.rows = list(rows)

    def briefing(self) -> dict[str, Any]:
        return catalog_products_briefing(self.rows)

    def story(self) -> list[str]:
        return catalog_products_weekly_story(self.rows)

    def csv(self) -> str:
        return '\n'.join(catalog_products_csv_lines(self.rows)) + '\n'

    def pack(self) -> dict[str, Any]:
        return catalog_products_print_pack(self.rows)


def build_catalog_products_reporter(rows: list[dict[str, Any]]) -> CatalogProductsReporter:
    return CatalogProductsReporter(rows)

def catalog_products_report_by_sku(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Product Catalog by Sku."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('sku') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'sku'} for label, count in ranked]


def catalog_products_report_by_name(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Product Catalog by Name."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('name') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'name'} for label, count in ranked]


def catalog_products_report_by_family(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Product Catalog by Family."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('family') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'family'} for label, count in ranked]


def catalog_products_report_by_list_cents(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Product Catalog by List Cents."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('list_cents') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'list_cents'} for label, count in ranked]


def catalog_products_outlier_list_cents(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    values = []
    for row in rows:
        try:
            values.append(int(row.get('list_cents') or 0))
        except (TypeError, ValueError):
            values.append(0)
    if not values:
        return []
    avg = sum(values) / len(values)
    flagged = []
    for row, value in zip(rows, values):
        if value > avg * 3 and value > 0:
            flagged.append({'id': row.get('id'), 'field': 'list_cents', 'value': value, 'avg': int(avg)})
    return flagged


def catalog_products_report_by_status(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Product Catalog by Status."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('status') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'status'} for label, count in ranked]


