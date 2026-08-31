"""Read models and search helpers for Benefits Plans."""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

DOMAIN_KEY = 'benefits_plans'
INDEX_FIELDS = ['plan_code', 'plan_name', 'eligibility', 'opens_on', 'status']


def benefits_plans_match(row: dict[str, Any], needle: str) -> bool:
    if not needle:
        return True
    blob = ' '.join(str(row.get(name, '')) for name in INDEX_FIELDS).lower()
    blob += ' ' + str(row.get('id') or '').lower()
    return needle.lower() in blob


def benefits_plans_apply_filters(rows: list[dict[str, Any]], filters: dict[str, Any] | None) -> list[dict[str, Any]]:
    filters = filters or {}
    needle = str(filters.get('q') or '').strip()
    status = str(filters.get('status') or '').strip()
    selected = []
    for row in rows:
        if status and str(row.get('status') or '') != status:
            continue
        if not benefits_plans_match(row, needle):
            continue
        selected.append(row)
    return selected


def benefits_plans_sort_rows(rows: list[dict[str, Any]], field: str = 'updated_at', reverse: bool = True) -> list[dict[str, Any]]:
    def keyfn(row: dict[str, Any]) -> str:
        return str(row.get(field) or '')
    return sorted(rows, key=keyfn, reverse=reverse)


def benefits_plans_page(rows: list[dict[str, Any]], offset: int = 0, limit: int = 50) -> list[dict[str, Any]]:
    if offset < 0:
        offset = 0
    if limit < 1:
        limit = 50
    if limit > 500:
        limit = 500
    return rows[offset: offset + limit]


def benefits_plans_group_status(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {name: [] for name in ['draft', 'open', 'closed']}
    grouped['other'] = []
    for row in rows:
        status = str(row.get('status') or '')
        if status in grouped:
            grouped[status].append(row)
        else:
            grouped['other'].append(row)
    return grouped


def benefits_plans_histogram(rows: list[dict[str, Any]], field: str) -> list[tuple[str, int]]:
    counter: Counter[str] = Counter()
    for row in rows:
        counter[str(row.get(field) or 'blank')] += 1
    return counter.most_common()


def benefits_plans_duplicates(rows: list[dict[str, Any]], field: str = 'plan_code') -> list[str]:
    seen: dict[str, int] = defaultdict(int)
    for row in rows:
        seen[str(row.get(field) or '')] += 1
    return [key for key, count in seen.items() if key and count > 1]


def benefits_plans_missing_required(rows: list[dict[str, Any]], required: list[str]) -> list[str]:
    missing = []
    for row in rows:
        for name in required:
            if not str(row.get(name) or '').strip():
                missing.append(str(row.get('id') or '') + ':' + name)
    return missing


def benefits_plans_health_bands(rows: list[dict[str, Any]]) -> dict[str, int]:
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


def benefits_plans_search_tokens(row: dict[str, Any]) -> set[str]:
    tokens: set[str] = set()
    for name in INDEX_FIELDS:
        value = str(row.get(name) or '').lower()
        for part in value.replace('/', ' ').replace('-', ' ').split():
            if len(part) >= 2:
                tokens.add(part)
    return tokens


def benefits_plans_suggest(rows: list[dict[str, Any]], prefix: str, limit: int = 8) -> list[str]:
    prefix = prefix.lower().strip()
    hits: list[str] = []
    if not prefix:
        return hits
    for row in rows:
        label = str(row.get('plan_code') or row.get('id') or '')
        if prefix in label.lower() and label not in hits:
            hits.append(label)
        if len(hits) >= limit:
            break
    return hits


def benefits_plans_export_map(row: dict[str, Any]) -> dict[str, str]:
    payload = {'id': str(row.get('id') or '')}
    for name in INDEX_FIELDS:
        payload[name] = str(row.get(name) or '')
    payload['health_score'] = str(row.get('health_score') or '')
    payload['updated_at'] = str(row.get('updated_at') or '')
    return payload


def benefits_plans_diff(before: dict[str, Any], after: dict[str, Any]) -> list[dict[str, str]]:
    changes = []
    keys = set(before) | set(after)
    for name in sorted(keys):
        left = str(before.get(name) or '')
        right = str(after.get(name) or '')
        if left != right:
            changes.append({'field': name, 'from': left, 'to': right})
    return changes


def benefits_plans_related_status(rows: list[dict[str, Any]], status: str) -> list[dict[str, Any]]:
    return [row for row in rows if str(row.get('status') or '') == status]


def benefits_plans_oldest(rows: list[dict[str, Any]], count: int = 5) -> list[dict[str, Any]]:
    ordered = benefits_plans_sort_rows(rows, field='created_at', reverse=False)
    return ordered[:count]


def benefits_plans_newest(rows: list[dict[str, Any]], count: int = 5) -> list[dict[str, Any]]:
    ordered = benefits_plans_sort_rows(rows, field='created_at', reverse=True)
    return ordered[:count]


def benefits_plans_attention_queue(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    queue = [row for row in rows if int(row.get('health_score') or 0) < 50]
    return benefits_plans_sort_rows(queue, field='health_score', reverse=False)


def benefits_plans_completeness(row: dict[str, Any]) -> int:
    filled = 0
    for name in INDEX_FIELDS:
        if str(row.get(name) or '').strip():
            filled += 1
    if not INDEX_FIELDS:
        return 0
    return int((filled / len(INDEX_FIELDS)) * 100)


def benefits_plans_board(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'total': len(rows),
        'bands': benefits_plans_health_bands(rows),
        'attention': len(benefits_plans_attention_queue(rows)),
        'newest': benefits_plans_newest(rows, 3),
        'oldest': benefits_plans_oldest(rows, 3),
    }

def benefits_plans_values_plan_code(rows: list[dict[str, Any]]) -> list[str]:
    """Distinct Plan Code values used in Benefits Plans."""
    values = []
    seen: set[str] = set()
    for row in rows:
        item = str(row.get('plan_code') or '')
        if item and item not in seen:
            seen.add(item)
            values.append(item)
    return values


def benefits_plans_filter_plan_code(rows: list[dict[str, Any]], expected: str) -> list[dict[str, Any]]:
    wanted = str(expected or '').strip()
    if not wanted:
        return list(rows)
    return [row for row in rows if str(row.get('plan_code') or '') == wanted]


def benefits_plans_values_plan_name(rows: list[dict[str, Any]]) -> list[str]:
    """Distinct Plan Name values used in Benefits Plans."""
    values = []
    seen: set[str] = set()
    for row in rows:
        item = str(row.get('plan_name') or '')
        if item and item not in seen:
            seen.add(item)
            values.append(item)
    return values


def benefits_plans_filter_plan_name(rows: list[dict[str, Any]], expected: str) -> list[dict[str, Any]]:
    wanted = str(expected or '').strip()
    if not wanted:
        return list(rows)
    return [row for row in rows if str(row.get('plan_name') or '') == wanted]


def benefits_plans_values_eligibility(rows: list[dict[str, Any]]) -> list[str]:
    """Distinct Eligibility values used in Benefits Plans."""
    values = []
    seen: set[str] = set()
    for row in rows:
        item = str(row.get('eligibility') or '')
        if item and item not in seen:
            seen.add(item)
            values.append(item)
    return values


def benefits_plans_filter_eligibility(rows: list[dict[str, Any]], expected: str) -> list[dict[str, Any]]:
    wanted = str(expected or '').strip()
    if not wanted:
        return list(rows)
    return [row for row in rows if str(row.get('eligibility') or '') == wanted]


def benefits_plans_values_opens_on(rows: list[dict[str, Any]]) -> list[str]:
    """Distinct Opens On values used in Benefits Plans."""
    values = []
    seen: set[str] = set()
    for row in rows:
        item = str(row.get('opens_on') or '')
        if item and item not in seen:
            seen.add(item)
            values.append(item)
    return values


def benefits_plans_filter_opens_on(rows: list[dict[str, Any]], expected: str) -> list[dict[str, Any]]:
    wanted = str(expected or '').strip()
    if not wanted:
        return list(rows)
    return [row for row in rows if str(row.get('opens_on') or '') == wanted]


def benefits_plans_values_status(rows: list[dict[str, Any]]) -> list[str]:
    """Distinct Status values used in Benefits Plans."""
    values = []
    seen: set[str] = set()
    for row in rows:
        item = str(row.get('status') or '')
        if item and item not in seen:
            seen.add(item)
            values.append(item)
    return values


def benefits_plans_filter_status(rows: list[dict[str, Any]], expected: str) -> list[dict[str, Any]]:
    wanted = str(expected or '').strip()
    if not wanted:
        return list(rows)
    return [row for row in rows if str(row.get('status') or '') == wanted]


