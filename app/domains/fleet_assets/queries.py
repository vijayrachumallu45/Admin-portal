"""Read models and search helpers for Fleet Assets."""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

DOMAIN_KEY = 'fleet_assets'
INDEX_FIELDS = ['asset_tag', 'kind', 'odometer', 'next_service', 'status']


def fleet_assets_match(row: dict[str, Any], needle: str) -> bool:
    if not needle:
        return True
    blob = ' '.join(str(row.get(name, '')) for name in INDEX_FIELDS).lower()
    blob += ' ' + str(row.get('id') or '').lower()
    return needle.lower() in blob


def fleet_assets_apply_filters(rows: list[dict[str, Any]], filters: dict[str, Any] | None) -> list[dict[str, Any]]:
    filters = filters or {}
    needle = str(filters.get('q') or '').strip()
    status = str(filters.get('status') or '').strip()
    selected = []
    for row in rows:
        if status and str(row.get('status') or '') != status:
            continue
        if not fleet_assets_match(row, needle):
            continue
        selected.append(row)
    return selected


def fleet_assets_sort_rows(rows: list[dict[str, Any]], field: str = 'updated_at', reverse: bool = True) -> list[dict[str, Any]]:
    def keyfn(row: dict[str, Any]) -> str:
        return str(row.get(field) or '')
    return sorted(rows, key=keyfn, reverse=reverse)


def fleet_assets_page(rows: list[dict[str, Any]], offset: int = 0, limit: int = 50) -> list[dict[str, Any]]:
    if offset < 0:
        offset = 0
    if limit < 1:
        limit = 50
    if limit > 500:
        limit = 500
    return rows[offset: offset + limit]


def fleet_assets_group_status(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {name: [] for name in ['ready', 'service', 'down', 'retired']}
    grouped['other'] = []
    for row in rows:
        status = str(row.get('status') or '')
        if status in grouped:
            grouped[status].append(row)
        else:
            grouped['other'].append(row)
    return grouped


def fleet_assets_histogram(rows: list[dict[str, Any]], field: str) -> list[tuple[str, int]]:
    counter: Counter[str] = Counter()
    for row in rows:
        counter[str(row.get(field) or 'blank')] += 1
    return counter.most_common()


def fleet_assets_duplicates(rows: list[dict[str, Any]], field: str = 'asset_tag') -> list[str]:
    seen: dict[str, int] = defaultdict(int)
    for row in rows:
        seen[str(row.get(field) or '')] += 1
    return [key for key, count in seen.items() if key and count > 1]


def fleet_assets_missing_required(rows: list[dict[str, Any]], required: list[str]) -> list[str]:
    missing = []
    for row in rows:
        for name in required:
            if not str(row.get(name) or '').strip():
                missing.append(str(row.get('id') or '') + ':' + name)
    return missing


def fleet_assets_health_bands(rows: list[dict[str, Any]]) -> dict[str, int]:
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


def fleet_assets_search_tokens(row: dict[str, Any]) -> set[str]:
    tokens: set[str] = set()
    for name in INDEX_FIELDS:
        value = str(row.get(name) or '').lower()
        for part in value.replace('/', ' ').replace('-', ' ').split():
            if len(part) >= 2:
                tokens.add(part)
    return tokens


def fleet_assets_suggest(rows: list[dict[str, Any]], prefix: str, limit: int = 8) -> list[str]:
    prefix = prefix.lower().strip()
    hits: list[str] = []
    if not prefix:
        return hits
    for row in rows:
        label = str(row.get('asset_tag') or row.get('id') or '')
        if prefix in label.lower() and label not in hits:
            hits.append(label)
        if len(hits) >= limit:
            break
    return hits


def fleet_assets_export_map(row: dict[str, Any]) -> dict[str, str]:
    payload = {'id': str(row.get('id') or '')}
    for name in INDEX_FIELDS:
        payload[name] = str(row.get(name) or '')
    payload['health_score'] = str(row.get('health_score') or '')
    payload['updated_at'] = str(row.get('updated_at') or '')
    return payload


def fleet_assets_diff(before: dict[str, Any], after: dict[str, Any]) -> list[dict[str, str]]:
    changes = []
    keys = set(before) | set(after)
    for name in sorted(keys):
        left = str(before.get(name) or '')
        right = str(after.get(name) or '')
        if left != right:
            changes.append({'field': name, 'from': left, 'to': right})
    return changes


def fleet_assets_related_status(rows: list[dict[str, Any]], status: str) -> list[dict[str, Any]]:
    return [row for row in rows if str(row.get('status') or '') == status]


def fleet_assets_oldest(rows: list[dict[str, Any]], count: int = 5) -> list[dict[str, Any]]:
    ordered = fleet_assets_sort_rows(rows, field='created_at', reverse=False)
    return ordered[:count]


def fleet_assets_newest(rows: list[dict[str, Any]], count: int = 5) -> list[dict[str, Any]]:
    ordered = fleet_assets_sort_rows(rows, field='created_at', reverse=True)
    return ordered[:count]


def fleet_assets_attention_queue(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    queue = [row for row in rows if int(row.get('health_score') or 0) < 50]
    return fleet_assets_sort_rows(queue, field='health_score', reverse=False)


def fleet_assets_completeness(row: dict[str, Any]) -> int:
    filled = 0
    for name in INDEX_FIELDS:
        if str(row.get(name) or '').strip():
            filled += 1
    if not INDEX_FIELDS:
        return 0
    return int((filled / len(INDEX_FIELDS)) * 100)


def fleet_assets_board(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'total': len(rows),
        'bands': fleet_assets_health_bands(rows),
        'attention': len(fleet_assets_attention_queue(rows)),
        'newest': fleet_assets_newest(rows, 3),
        'oldest': fleet_assets_oldest(rows, 3),
    }

def fleet_assets_values_asset_tag(rows: list[dict[str, Any]]) -> list[str]:
    """Distinct Asset Tag values used in Fleet Assets."""
    values = []
    seen: set[str] = set()
    for row in rows:
        item = str(row.get('asset_tag') or '')
        if item and item not in seen:
            seen.add(item)
            values.append(item)
    return values


def fleet_assets_filter_asset_tag(rows: list[dict[str, Any]], expected: str) -> list[dict[str, Any]]:
    wanted = str(expected or '').strip()
    if not wanted:
        return list(rows)
    return [row for row in rows if str(row.get('asset_tag') or '') == wanted]


def fleet_assets_values_kind(rows: list[dict[str, Any]]) -> list[str]:
    """Distinct Kind values used in Fleet Assets."""
    values = []
    seen: set[str] = set()
    for row in rows:
        item = str(row.get('kind') or '')
        if item and item not in seen:
            seen.add(item)
            values.append(item)
    return values


def fleet_assets_filter_kind(rows: list[dict[str, Any]], expected: str) -> list[dict[str, Any]]:
    wanted = str(expected or '').strip()
    if not wanted:
        return list(rows)
    return [row for row in rows if str(row.get('kind') or '') == wanted]


def fleet_assets_values_odometer(rows: list[dict[str, Any]]) -> list[str]:
    """Distinct Odometer values used in Fleet Assets."""
    values = []
    seen: set[str] = set()
    for row in rows:
        item = str(row.get('odometer') or '')
        if item and item not in seen:
            seen.add(item)
            values.append(item)
    return values


def fleet_assets_filter_odometer(rows: list[dict[str, Any]], expected: str) -> list[dict[str, Any]]:
    wanted = str(expected or '').strip()
    if not wanted:
        return list(rows)
    return [row for row in rows if str(row.get('odometer') or '') == wanted]


def fleet_assets_sum_odometer(rows: list[dict[str, Any]]) -> int:
    total = 0
    for row in rows:
        try:
            total += int(row.get('odometer') or 0)
        except (TypeError, ValueError):
            continue
    return total


def fleet_assets_avg_odometer(rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    return int(fleet_assets_sum_odometer(rows) / max(1, len(rows)))


def fleet_assets_values_next_service(rows: list[dict[str, Any]]) -> list[str]:
    """Distinct Next Service values used in Fleet Assets."""
    values = []
    seen: set[str] = set()
    for row in rows:
        item = str(row.get('next_service') or '')
        if item and item not in seen:
            seen.add(item)
            values.append(item)
    return values


def fleet_assets_filter_next_service(rows: list[dict[str, Any]], expected: str) -> list[dict[str, Any]]:
    wanted = str(expected or '').strip()
    if not wanted:
        return list(rows)
    return [row for row in rows if str(row.get('next_service') or '') == wanted]


def fleet_assets_values_status(rows: list[dict[str, Any]]) -> list[str]:
    """Distinct Status values used in Fleet Assets."""
    values = []
    seen: set[str] = set()
    for row in rows:
        item = str(row.get('status') or '')
        if item and item not in seen:
            seen.add(item)
            values.append(item)
    return values


def fleet_assets_filter_status(rows: list[dict[str, Any]], expected: str) -> list[dict[str, Any]]:
    wanted = str(expected or '').strip()
    if not wanted:
        return list(rows)
    return [row for row in rows if str(row.get('status') or '') == wanted]


