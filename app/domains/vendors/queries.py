"""Read models and search helpers for Vendor Register."""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

DOMAIN_KEY = 'vendors'
INDEX_FIELDS = ['vendor_code', 'name', 'category', 'country', 'risk_score', 'status']


def vendors_match(row: dict[str, Any], needle: str) -> bool:
    if not needle:
        return True
    blob = ' '.join(str(row.get(name, '')) for name in INDEX_FIELDS).lower()
    blob += ' ' + str(row.get('id') or '').lower()
    return needle.lower() in blob


def vendors_apply_filters(rows: list[dict[str, Any]], filters: dict[str, Any] | None) -> list[dict[str, Any]]:
    filters = filters or {}
    needle = str(filters.get('q') or '').strip()
    status = str(filters.get('status') or '').strip()
    selected = []
    for row in rows:
        if status and str(row.get('status') or '') != status:
            continue
        if not vendors_match(row, needle):
            continue
        selected.append(row)
    return selected


def vendors_sort_rows(rows: list[dict[str, Any]], field: str = 'updated_at', reverse: bool = True) -> list[dict[str, Any]]:
    def keyfn(row: dict[str, Any]) -> str:
        return str(row.get(field) or '')
    return sorted(rows, key=keyfn, reverse=reverse)


def vendors_page(rows: list[dict[str, Any]], offset: int = 0, limit: int = 50) -> list[dict[str, Any]]:
    if offset < 0:
        offset = 0
    if limit < 1:
        limit = 50
    if limit > 500:
        limit = 500
    return rows[offset: offset + limit]


def vendors_group_status(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {name: [] for name in ['screening', 'approved', 'watchlist', 'exited']}
    grouped['other'] = []
    for row in rows:
        status = str(row.get('status') or '')
        if status in grouped:
            grouped[status].append(row)
        else:
            grouped['other'].append(row)
    return grouped


def vendors_histogram(rows: list[dict[str, Any]], field: str) -> list[tuple[str, int]]:
    counter: Counter[str] = Counter()
    for row in rows:
        counter[str(row.get(field) or 'blank')] += 1
    return counter.most_common()


def vendors_duplicates(rows: list[dict[str, Any]], field: str = 'vendor_code') -> list[str]:
    seen: dict[str, int] = defaultdict(int)
    for row in rows:
        seen[str(row.get(field) or '')] += 1
    return [key for key, count in seen.items() if key and count > 1]


def vendors_missing_required(rows: list[dict[str, Any]], required: list[str]) -> list[str]:
    missing = []
    for row in rows:
        for name in required:
            if not str(row.get(name) or '').strip():
                missing.append(str(row.get('id') or '') + ':' + name)
    return missing


def vendors_health_bands(rows: list[dict[str, Any]]) -> dict[str, int]:
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


def vendors_search_tokens(row: dict[str, Any]) -> set[str]:
    tokens: set[str] = set()
    for name in INDEX_FIELDS:
        value = str(row.get(name) or '').lower()
        for part in value.replace('/', ' ').replace('-', ' ').split():
            if len(part) >= 2:
                tokens.add(part)
    return tokens


def vendors_suggest(rows: list[dict[str, Any]], prefix: str, limit: int = 8) -> list[str]:
    prefix = prefix.lower().strip()
    hits: list[str] = []
    if not prefix:
        return hits
    for row in rows:
        label = str(row.get('vendor_code') or row.get('id') or '')
        if prefix in label.lower() and label not in hits:
            hits.append(label)
        if len(hits) >= limit:
            break
    return hits


def vendors_export_map(row: dict[str, Any]) -> dict[str, str]:
    payload = {'id': str(row.get('id') or '')}
    for name in INDEX_FIELDS:
        payload[name] = str(row.get(name) or '')
    payload['health_score'] = str(row.get('health_score') or '')
    payload['updated_at'] = str(row.get('updated_at') or '')
    return payload


def vendors_diff(before: dict[str, Any], after: dict[str, Any]) -> list[dict[str, str]]:
    changes = []
    keys = set(before) | set(after)
    for name in sorted(keys):
        left = str(before.get(name) or '')
        right = str(after.get(name) or '')
        if left != right:
            changes.append({'field': name, 'from': left, 'to': right})
    return changes


def vendors_related_status(rows: list[dict[str, Any]], status: str) -> list[dict[str, Any]]:
    return [row for row in rows if str(row.get('status') or '') == status]


def vendors_oldest(rows: list[dict[str, Any]], count: int = 5) -> list[dict[str, Any]]:
    ordered = vendors_sort_rows(rows, field='created_at', reverse=False)
    return ordered[:count]


def vendors_newest(rows: list[dict[str, Any]], count: int = 5) -> list[dict[str, Any]]:
    ordered = vendors_sort_rows(rows, field='created_at', reverse=True)
    return ordered[:count]


def vendors_attention_queue(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    queue = [row for row in rows if int(row.get('health_score') or 0) < 50]
    return vendors_sort_rows(queue, field='health_score', reverse=False)


def vendors_completeness(row: dict[str, Any]) -> int:
    filled = 0
    for name in INDEX_FIELDS:
        if str(row.get(name) or '').strip():
            filled += 1
    if not INDEX_FIELDS:
        return 0
    return int((filled / len(INDEX_FIELDS)) * 100)


def vendors_board(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'total': len(rows),
        'bands': vendors_health_bands(rows),
        'attention': len(vendors_attention_queue(rows)),
        'newest': vendors_newest(rows, 3),
        'oldest': vendors_oldest(rows, 3),
    }

def vendors_values_vendor_code(rows: list[dict[str, Any]]) -> list[str]:
    """Distinct Vendor Code values used in Vendor Register."""
    values = []
    seen: set[str] = set()
    for row in rows:
        item = str(row.get('vendor_code') or '')
        if item and item not in seen:
            seen.add(item)
            values.append(item)
    return values


def vendors_filter_vendor_code(rows: list[dict[str, Any]], expected: str) -> list[dict[str, Any]]:
    wanted = str(expected or '').strip()
    if not wanted:
        return list(rows)
    return [row for row in rows if str(row.get('vendor_code') or '') == wanted]


def vendors_values_name(rows: list[dict[str, Any]]) -> list[str]:
    """Distinct Name values used in Vendor Register."""
    values = []
    seen: set[str] = set()
    for row in rows:
        item = str(row.get('name') or '')
        if item and item not in seen:
            seen.add(item)
            values.append(item)
    return values


def vendors_filter_name(rows: list[dict[str, Any]], expected: str) -> list[dict[str, Any]]:
    wanted = str(expected or '').strip()
    if not wanted:
        return list(rows)
    return [row for row in rows if str(row.get('name') or '') == wanted]


def vendors_values_category(rows: list[dict[str, Any]]) -> list[str]:
    """Distinct Category values used in Vendor Register."""
    values = []
    seen: set[str] = set()
    for row in rows:
        item = str(row.get('category') or '')
        if item and item not in seen:
            seen.add(item)
            values.append(item)
    return values


def vendors_filter_category(rows: list[dict[str, Any]], expected: str) -> list[dict[str, Any]]:
    wanted = str(expected or '').strip()
    if not wanted:
        return list(rows)
    return [row for row in rows if str(row.get('category') or '') == wanted]


def vendors_values_country(rows: list[dict[str, Any]]) -> list[str]:
    """Distinct Country values used in Vendor Register."""
    values = []
    seen: set[str] = set()
    for row in rows:
        item = str(row.get('country') or '')
        if item and item not in seen:
            seen.add(item)
            values.append(item)
    return values


def vendors_filter_country(rows: list[dict[str, Any]], expected: str) -> list[dict[str, Any]]:
    wanted = str(expected or '').strip()
    if not wanted:
        return list(rows)
    return [row for row in rows if str(row.get('country') or '') == wanted]


def vendors_values_risk_score(rows: list[dict[str, Any]]) -> list[str]:
    """Distinct Risk Score values used in Vendor Register."""
    values = []
    seen: set[str] = set()
    for row in rows:
        item = str(row.get('risk_score') or '')
        if item and item not in seen:
            seen.add(item)
            values.append(item)
    return values


def vendors_filter_risk_score(rows: list[dict[str, Any]], expected: str) -> list[dict[str, Any]]:
    wanted = str(expected or '').strip()
    if not wanted:
        return list(rows)
    return [row for row in rows if str(row.get('risk_score') or '') == wanted]


def vendors_sum_risk_score(rows: list[dict[str, Any]]) -> int:
    total = 0
    for row in rows:
        try:
            total += int(row.get('risk_score') or 0)
        except (TypeError, ValueError):
            continue
    return total


def vendors_avg_risk_score(rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    return int(vendors_sum_risk_score(rows) / max(1, len(rows)))


def vendors_values_status(rows: list[dict[str, Any]]) -> list[str]:
    """Distinct Status values used in Vendor Register."""
    values = []
    seen: set[str] = set()
    for row in rows:
        item = str(row.get('status') or '')
        if item and item not in seen:
            seen.add(item)
            values.append(item)
    return values


def vendors_filter_status(rows: list[dict[str, Any]], expected: str) -> list[dict[str, Any]]:
    wanted = str(expected or '').strip()
    if not wanted:
        return list(rows)
    return [row for row in rows if str(row.get('status') or '') == wanted]


