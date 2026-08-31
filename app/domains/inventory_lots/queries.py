"""Read models and search helpers for Inventory Lots."""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

DOMAIN_KEY = 'inventory_lots'
INDEX_FIELDS = ['sku', 'warehouse', 'on_hand', 'reserved', 'reorder_at', 'status']


def inventory_lots_match(row: dict[str, Any], needle: str) -> bool:
    if not needle:
        return True
    blob = ' '.join(str(row.get(name, '')) for name in INDEX_FIELDS).lower()
    blob += ' ' + str(row.get('id') or '').lower()
    return needle.lower() in blob


def inventory_lots_apply_filters(rows: list[dict[str, Any]], filters: dict[str, Any] | None) -> list[dict[str, Any]]:
    filters = filters or {}
    needle = str(filters.get('q') or '').strip()
    status = str(filters.get('status') or '').strip()
    selected = []
    for row in rows:
        if status and str(row.get('status') or '') != status:
            continue
        if not inventory_lots_match(row, needle):
            continue
        selected.append(row)
    return selected


def inventory_lots_sort_rows(rows: list[dict[str, Any]], field: str = 'updated_at', reverse: bool = True) -> list[dict[str, Any]]:
    def keyfn(row: dict[str, Any]) -> str:
        return str(row.get(field) or '')
    return sorted(rows, key=keyfn, reverse=reverse)


def inventory_lots_page(rows: list[dict[str, Any]], offset: int = 0, limit: int = 50) -> list[dict[str, Any]]:
    if offset < 0:
        offset = 0
    if limit < 1:
        limit = 50
    if limit > 500:
        limit = 500
    return rows[offset: offset + limit]


def inventory_lots_group_status(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {name: [] for name in ['available', 'held', 'quarantine', 'depleted']}
    grouped['other'] = []
    for row in rows:
        status = str(row.get('status') or '')
        if status in grouped:
            grouped[status].append(row)
        else:
            grouped['other'].append(row)
    return grouped


def inventory_lots_histogram(rows: list[dict[str, Any]], field: str) -> list[tuple[str, int]]:
    counter: Counter[str] = Counter()
    for row in rows:
        counter[str(row.get(field) or 'blank')] += 1
    return counter.most_common()


def inventory_lots_duplicates(rows: list[dict[str, Any]], field: str = 'sku') -> list[str]:
    seen: dict[str, int] = defaultdict(int)
    for row in rows:
        seen[str(row.get(field) or '')] += 1
    return [key for key, count in seen.items() if key and count > 1]


def inventory_lots_missing_required(rows: list[dict[str, Any]], required: list[str]) -> list[str]:
    missing = []
    for row in rows:
        for name in required:
            if not str(row.get(name) or '').strip():
                missing.append(str(row.get('id') or '') + ':' + name)
    return missing


def inventory_lots_health_bands(rows: list[dict[str, Any]]) -> dict[str, int]:
    bands = {'calm': 0, 'watch': 0, 'elevated': 0, 'critical': 0}
    for row in rows:
        score = int(row.get('health_score') or 0)
        if score >= 80:
            bands['calm'] += 1
        elif score >= 55:
            bands['watch'] += 1
        elif score >= 30:
            bands['elevated'] += 1
        else:
            bands['critical'] += 1
    return bands


def inventory_lots_search_tokens(row: dict[str, Any]) -> set[str]:
    tokens: set[str] = set()
    for name in INDEX_FIELDS:
        value = str(row.get(name) or '').lower()
        for part in value.replace('/', ' ').replace('-', ' ').split():
            if len(part) >= 2:
                tokens.add(part)
    return tokens


def inventory_lots_suggest(rows: list[dict[str, Any]], prefix: str, limit: int = 8) -> list[str]:
    prefix = prefix.lower().strip()
    hits: list[str] = []
    if not prefix:
        return hits
    for row in rows:
        label = str(row.get('sku') or row.get('id') or '')
        if prefix in label.lower() and label not in hits:
            hits.append(label)
        if len(hits) >= limit:
            break
    return hits


def inventory_lots_export_map(row: dict[str, Any]) -> dict[str, str]:
    payload = {'id': str(row.get('id') or '')}
    for name in INDEX_FIELDS:
        payload[name] = str(row.get(name) or '')
    payload['health_score'] = str(row.get('health_score') or '')
    payload['updated_at'] = str(row.get('updated_at') or '')
    return payload


def inventory_lots_diff(before: dict[str, Any], after: dict[str, Any]) -> list[dict[str, str]]:
    changes = []
    keys = set(before) | set(after)
    for name in sorted(keys):
        left = str(before.get(name) or '')
        right = str(after.get(name) or '')
        if left != right:
            changes.append({'field': name, 'from': left, 'to': right})
    return changes


def inventory_lots_related_status(rows: list[dict[str, Any]], status: str) -> list[dict[str, Any]]:
    return [row for row in rows if str(row.get('status') or '') == status]


def inventory_lots_oldest(rows: list[dict[str, Any]], count: int = 5) -> list[dict[str, Any]]:
    ordered = inventory_lots_sort_rows(rows, field='created_at', reverse=False)
    return ordered[:count]


def inventory_lots_newest(rows: list[dict[str, Any]], count: int = 5) -> list[dict[str, Any]]:
    ordered = inventory_lots_sort_rows(rows, field='created_at', reverse=True)
    return ordered[:count]


def inventory_lots_attention_queue(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    queue = [row for row in rows if int(row.get('health_score') or 0) < 50]
    return inventory_lots_sort_rows(queue, field='health_score', reverse=False)


def inventory_lots_completeness(row: dict[str, Any]) -> int:
    filled = 0
    for name in INDEX_FIELDS:
        if str(row.get(name) or '').strip():
            filled += 1
    if not INDEX_FIELDS:
        return 0
    return int((filled / len(INDEX_FIELDS)) * 100)


def inventory_lots_board(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'total': len(rows),
        'bands': inventory_lots_health_bands(rows),
        'attention': len(inventory_lots_attention_queue(rows)),
        'newest': inventory_lots_newest(rows, 3),
        'oldest': inventory_lots_oldest(rows, 3),
    }

def inventory_lots_values_sku(rows: list[dict[str, Any]]) -> list[str]:
    """Distinct Sku values used in Inventory Lots."""
    values = []
    seen: set[str] = set()
    for row in rows:
        item = str(row.get('sku') or '')
        if item and item not in seen:
            seen.add(item)
            values.append(item)
    return values


def inventory_lots_filter_sku(rows: list[dict[str, Any]], expected: str) -> list[dict[str, Any]]:
    wanted = str(expected or '').strip()
    if not wanted:
        return list(rows)
    return [row for row in rows if str(row.get('sku') or '') == wanted]


def inventory_lots_values_warehouse(rows: list[dict[str, Any]]) -> list[str]:
    """Distinct Warehouse values used in Inventory Lots."""
    values = []
    seen: set[str] = set()
    for row in rows:
        item = str(row.get('warehouse') or '')
        if item and item not in seen:
            seen.add(item)
            values.append(item)
    return values


def inventory_lots_filter_warehouse(rows: list[dict[str, Any]], expected: str) -> list[dict[str, Any]]:
    wanted = str(expected or '').strip()
    if not wanted:
        return list(rows)
    return [row for row in rows if str(row.get('warehouse') or '') == wanted]


def inventory_lots_values_on_hand(rows: list[dict[str, Any]]) -> list[str]:
    """Distinct On Hand values used in Inventory Lots."""
    values = []
    seen: set[str] = set()
    for row in rows:
        item = str(row.get('on_hand') or '')
        if item and item not in seen:
            seen.add(item)
            values.append(item)
    return values


def inventory_lots_filter_on_hand(rows: list[dict[str, Any]], expected: str) -> list[dict[str, Any]]:
    wanted = str(expected or '').strip()
    if not wanted:
        return list(rows)
    return [row for row in rows if str(row.get('on_hand') or '') == wanted]


def inventory_lots_sum_on_hand(rows: list[dict[str, Any]]) -> int:
    total = 0
    for row in rows:
        try:
            total += int(row.get('on_hand') or 0)
        except (TypeError, ValueError):
            continue
    return total


def inventory_lots_avg_on_hand(rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    return int(inventory_lots_sum_on_hand(rows) / max(1, len(rows)))


def inventory_lots_values_reserved(rows: list[dict[str, Any]]) -> list[str]:
    """Distinct Reserved values used in Inventory Lots."""
    values = []
    seen: set[str] = set()
    for row in rows:
        item = str(row.get('reserved') or '')
        if item and item not in seen:
            seen.add(item)
            values.append(item)
    return values


def inventory_lots_filter_reserved(rows: list[dict[str, Any]], expected: str) -> list[dict[str, Any]]:
    wanted = str(expected or '').strip()
    if not wanted:
        return list(rows)
    return [row for row in rows if str(row.get('reserved') or '') == wanted]


def inventory_lots_sum_reserved(rows: list[dict[str, Any]]) -> int:
    total = 0
    for row in rows:
        try:
            total += int(row.get('reserved') or 0)
        except (TypeError, ValueError):
            continue
    return total


def inventory_lots_avg_reserved(rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    return int(inventory_lots_sum_reserved(rows) / max(1, len(rows)))


def inventory_lots_values_reorder_at(rows: list[dict[str, Any]]) -> list[str]:
    """Distinct Reorder At values used in Inventory Lots."""
    values = []
    seen: set[str] = set()
    for row in rows:
        item = str(row.get('reorder_at') or '')
        if item and item not in seen:
            seen.add(item)
            values.append(item)
    return values


def inventory_lots_filter_reorder_at(rows: list[dict[str, Any]], expected: str) -> list[dict[str, Any]]:
    wanted = str(expected or '').strip()
    if not wanted:
        return list(rows)
    return [row for row in rows if str(row.get('reorder_at') or '') == wanted]


def inventory_lots_sum_reorder_at(rows: list[dict[str, Any]]) -> int:
    total = 0
    for row in rows:
        try:
            total += int(row.get('reorder_at') or 0)
        except (TypeError, ValueError):
            continue
    return total


def inventory_lots_avg_reorder_at(rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    return int(inventory_lots_sum_reorder_at(rows) / max(1, len(rows)))


def inventory_lots_values_status(rows: list[dict[str, Any]]) -> list[str]:
    """Distinct Status values used in Inventory Lots."""
    values = []
    seen: set[str] = set()
    for row in rows:
        item = str(row.get('status') or '')
        if item and item not in seen:
            seen.add(item)
            values.append(item)
    return values


def inventory_lots_filter_status(rows: list[dict[str, Any]], expected: str) -> list[dict[str, Any]]:
    wanted = str(expected or '').strip()
    if not wanted:
        return list(rows)
    return [row for row in rows if str(row.get('status') or '') == wanted]


