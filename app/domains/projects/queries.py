"""Read models and search helpers for Delivery Projects."""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

DOMAIN_KEY = 'projects'
INDEX_FIELDS = ['project_code', 'name', 'sponsor', 'budget_cents', 'health', 'status']


def projects_match(row: dict[str, Any], needle: str) -> bool:
    if not needle:
        return True
    blob = ' '.join(str(row.get(name, '')) for name in INDEX_FIELDS).lower()
    blob += ' ' + str(row.get('id') or '').lower()
    return needle.lower() in blob


def projects_apply_filters(rows: list[dict[str, Any]], filters: dict[str, Any] | None) -> list[dict[str, Any]]:
    filters = filters or {}
    needle = str(filters.get('q') or '').strip()
    status = str(filters.get('status') or '').strip()
    selected = []
    for row in rows:
        if status and str(row.get('status') or '') != status:
            continue
        if not projects_match(row, needle):
            continue
        selected.append(row)
    return selected


def projects_sort_rows(rows: list[dict[str, Any]], field: str = 'updated_at', reverse: bool = True) -> list[dict[str, Any]]:
    def keyfn(row: dict[str, Any]) -> str:
        return str(row.get(field) or '')
    return sorted(rows, key=keyfn, reverse=reverse)


def projects_page(rows: list[dict[str, Any]], offset: int = 0, limit: int = 50) -> list[dict[str, Any]]:
    if offset < 0:
        offset = 0
    if limit < 1:
        limit = 50
    if limit > 500:
        limit = 500
    return rows[offset: offset + limit]


def projects_group_status(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {name: [] for name in ['planning', 'active', 'blocked', 'done']}
    grouped['other'] = []
    for row in rows:
        status = str(row.get('status') or '')
        if status in grouped:
            grouped[status].append(row)
        else:
            grouped['other'].append(row)
    return grouped


def projects_histogram(rows: list[dict[str, Any]], field: str) -> list[tuple[str, int]]:
    counter: Counter[str] = Counter()
    for row in rows:
        counter[str(row.get(field) or 'blank')] += 1
    return counter.most_common()


def projects_duplicates(rows: list[dict[str, Any]], field: str = 'project_code') -> list[str]:
    seen: dict[str, int] = defaultdict(int)
    for row in rows:
        seen[str(row.get(field) or '')] += 1
    return [key for key, count in seen.items() if key and count > 1]


def projects_missing_required(rows: list[dict[str, Any]], required: list[str]) -> list[str]:
    missing = []
    for row in rows:
        for name in required:
            if not str(row.get(name) or '').strip():
                missing.append(str(row.get('id') or '') + ':' + name)
    return missing


def projects_health_bands(rows: list[dict[str, Any]]) -> dict[str, int]:
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


def projects_search_tokens(row: dict[str, Any]) -> set[str]:
    tokens: set[str] = set()
    for name in INDEX_FIELDS:
        value = str(row.get(name) or '').lower()
        for part in value.replace('/', ' ').replace('-', ' ').split():
            if len(part) >= 2:
                tokens.add(part)
    return tokens


def projects_suggest(rows: list[dict[str, Any]], prefix: str, limit: int = 8) -> list[str]:
    prefix = prefix.lower().strip()
    hits: list[str] = []
    if not prefix:
        return hits
    for row in rows:
        label = str(row.get('project_code') or row.get('id') or '')
        if prefix in label.lower() and label not in hits:
            hits.append(label)
        if len(hits) >= limit:
            break
    return hits


def projects_export_map(row: dict[str, Any]) -> dict[str, str]:
    payload = {'id': str(row.get('id') or '')}
    for name in INDEX_FIELDS:
        payload[name] = str(row.get(name) or '')
    payload['health_score'] = str(row.get('health_score') or '')
    payload['updated_at'] = str(row.get('updated_at') or '')
    return payload


def projects_diff(before: dict[str, Any], after: dict[str, Any]) -> list[dict[str, str]]:
    changes = []
    keys = set(before) | set(after)
    for name in sorted(keys):
        left = str(before.get(name) or '')
        right = str(after.get(name) or '')
        if left != right:
            changes.append({'field': name, 'from': left, 'to': right})
    return changes


def projects_related_status(rows: list[dict[str, Any]], status: str) -> list[dict[str, Any]]:
    return [row for row in rows if str(row.get('status') or '') == status]


def projects_oldest(rows: list[dict[str, Any]], count: int = 5) -> list[dict[str, Any]]:
    ordered = projects_sort_rows(rows, field='created_at', reverse=False)
    return ordered[:count]


def projects_newest(rows: list[dict[str, Any]], count: int = 5) -> list[dict[str, Any]]:
    ordered = projects_sort_rows(rows, field='created_at', reverse=True)
    return ordered[:count]


def projects_attention_queue(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    queue = [row for row in rows if int(row.get('health_score') or 0) < 50]
    return projects_sort_rows(queue, field='health_score', reverse=False)


def projects_completeness(row: dict[str, Any]) -> int:
    filled = 0
    for name in INDEX_FIELDS:
        if str(row.get(name) or '').strip():
            filled += 1
    if not INDEX_FIELDS:
        return 0
    return int((filled / len(INDEX_FIELDS)) * 100)


def projects_board(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'total': len(rows),
        'bands': projects_health_bands(rows),
        'attention': len(projects_attention_queue(rows)),
        'newest': projects_newest(rows, 3),
        'oldest': projects_oldest(rows, 3),
    }

def projects_values_project_code(rows: list[dict[str, Any]]) -> list[str]:
    """Distinct Project Code values used in Delivery Projects."""
    values = []
    seen: set[str] = set()
    for row in rows:
        item = str(row.get('project_code') or '')
        if item and item not in seen:
            seen.add(item)
            values.append(item)
    return values


def projects_filter_project_code(rows: list[dict[str, Any]], expected: str) -> list[dict[str, Any]]:
    wanted = str(expected or '').strip()
    if not wanted:
        return list(rows)
    return [row for row in rows if str(row.get('project_code') or '') == wanted]


def projects_values_name(rows: list[dict[str, Any]]) -> list[str]:
    """Distinct Name values used in Delivery Projects."""
    values = []
    seen: set[str] = set()
    for row in rows:
        item = str(row.get('name') or '')
        if item and item not in seen:
            seen.add(item)
            values.append(item)
    return values


def projects_filter_name(rows: list[dict[str, Any]], expected: str) -> list[dict[str, Any]]:
    wanted = str(expected or '').strip()
    if not wanted:
        return list(rows)
    return [row for row in rows if str(row.get('name') or '') == wanted]


def projects_values_sponsor(rows: list[dict[str, Any]]) -> list[str]:
    """Distinct Sponsor values used in Delivery Projects."""
    values = []
    seen: set[str] = set()
    for row in rows:
        item = str(row.get('sponsor') or '')
        if item and item not in seen:
            seen.add(item)
            values.append(item)
    return values


def projects_filter_sponsor(rows: list[dict[str, Any]], expected: str) -> list[dict[str, Any]]:
    wanted = str(expected or '').strip()
    if not wanted:
        return list(rows)
    return [row for row in rows if str(row.get('sponsor') or '') == wanted]


def projects_values_budget_cents(rows: list[dict[str, Any]]) -> list[str]:
    """Distinct Budget Cents values used in Delivery Projects."""
    values = []
    seen: set[str] = set()
    for row in rows:
        item = str(row.get('budget_cents') or '')
        if item and item not in seen:
            seen.add(item)
            values.append(item)
    return values


def projects_filter_budget_cents(rows: list[dict[str, Any]], expected: str) -> list[dict[str, Any]]:
    wanted = str(expected or '').strip()
    if not wanted:
        return list(rows)
    return [row for row in rows if str(row.get('budget_cents') or '') == wanted]


def projects_sum_budget_cents(rows: list[dict[str, Any]]) -> int:
    total = 0
    for row in rows:
        try:
            total += int(row.get('budget_cents') or 0)
        except (TypeError, ValueError):
            continue
    return total


def projects_avg_budget_cents(rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    return int(projects_sum_budget_cents(rows) / max(1, len(rows)))


def projects_values_health(rows: list[dict[str, Any]]) -> list[str]:
    """Distinct Health values used in Delivery Projects."""
    values = []
    seen: set[str] = set()
    for row in rows:
        item = str(row.get('health') or '')
        if item and item not in seen:
            seen.add(item)
            values.append(item)
    return values


def projects_filter_health(rows: list[dict[str, Any]], expected: str) -> list[dict[str, Any]]:
    wanted = str(expected or '').strip()
    if not wanted:
        return list(rows)
    return [row for row in rows if str(row.get('health') or '') == wanted]


def projects_values_status(rows: list[dict[str, Any]]) -> list[str]:
    """Distinct Status values used in Delivery Projects."""
    values = []
    seen: set[str] = set()
    for row in rows:
        item = str(row.get('status') or '')
        if item and item not in seen:
            seen.add(item)
            values.append(item)
    return values


def projects_filter_status(rows: list[dict[str, Any]], expected: str) -> list[dict[str, Any]]:
    wanted = str(expected or '').strip()
    if not wanted:
        return list(rows)
    return [row for row in rows if str(row.get('status') or '') == wanted]


