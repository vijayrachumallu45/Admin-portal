"""Read models and search helpers for Incident Room."""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

DOMAIN_KEY = 'incidents'
INDEX_FIELDS = ['incident_no', 'title', 'severity', 'commander', 'started_at', 'status']


def incidents_match(row: dict[str, Any], needle: str) -> bool:
    if not needle:
        return True
    blob = ' '.join(str(row.get(name, '')) for name in INDEX_FIELDS).lower()
    blob += ' ' + str(row.get('id') or '').lower()
    return needle.lower() in blob


def incidents_apply_filters(rows: list[dict[str, Any]], filters: dict[str, Any] | None) -> list[dict[str, Any]]:
    filters = filters or {}
    needle = str(filters.get('q') or '').strip()
    status = str(filters.get('status') or '').strip()
    selected = []
    for row in rows:
        if status and str(row.get('status') or '') != status:
            continue
        if not incidents_match(row, needle):
            continue
        selected.append(row)
    return selected


def incidents_sort_rows(rows: list[dict[str, Any]], field: str = 'updated_at', reverse: bool = True) -> list[dict[str, Any]]:
    def keyfn(row: dict[str, Any]) -> str:
        return str(row.get(field) or '')
    return sorted(rows, key=keyfn, reverse=reverse)


def incidents_page(rows: list[dict[str, Any]], offset: int = 0, limit: int = 50) -> list[dict[str, Any]]:
    if offset < 0:
        offset = 0
    if limit < 1:
        limit = 50
    if limit > 500:
        limit = 500
    return rows[offset: offset + limit]


def incidents_group_status(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {name: [] for name in ['investigating', 'identified', 'monitoring', 'resolved']}
    grouped['other'] = []
    for row in rows:
        status = str(row.get('status') or '')
        if status in grouped:
            grouped[status].append(row)
        else:
            grouped['other'].append(row)
    return grouped


def incidents_histogram(rows: list[dict[str, Any]], field: str) -> list[tuple[str, int]]:
    counter: Counter[str] = Counter()
    for row in rows:
        counter[str(row.get(field) or 'blank')] += 1
    return counter.most_common()


def incidents_duplicates(rows: list[dict[str, Any]], field: str = 'incident_no') -> list[str]:
    seen: dict[str, int] = defaultdict(int)
    for row in rows:
        seen[str(row.get(field) or '')] += 1
    return [key for key, count in seen.items() if key and count > 1]


def incidents_missing_required(rows: list[dict[str, Any]], required: list[str]) -> list[str]:
    missing = []
    for row in rows:
        for name in required:
            if not str(row.get(name) or '').strip():
                missing.append(str(row.get('id') or '') + ':' + name)
    return missing


def incidents_health_bands(rows: list[dict[str, Any]]) -> dict[str, int]:
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


def incidents_search_tokens(row: dict[str, Any]) -> set[str]:
    tokens: set[str] = set()
    for name in INDEX_FIELDS:
        value = str(row.get(name) or '').lower()
        for part in value.replace('/', ' ').replace('-', ' ').split():
            if len(part) >= 2:
                tokens.add(part)
    return tokens


def incidents_suggest(rows: list[dict[str, Any]], prefix: str, limit: int = 8) -> list[str]:
    prefix = prefix.lower().strip()
    hits: list[str] = []
    if not prefix:
        return hits
    for row in rows:
        label = str(row.get('incident_no') or row.get('id') or '')
        if prefix in label.lower() and label not in hits:
            hits.append(label)
        if len(hits) >= limit:
            break
    return hits


def incidents_export_map(row: dict[str, Any]) -> dict[str, str]:
    payload = {'id': str(row.get('id') or '')}
    for name in INDEX_FIELDS:
        payload[name] = str(row.get(name) or '')
    payload['health_score'] = str(row.get('health_score') or '')
    payload['updated_at'] = str(row.get('updated_at') or '')
    return payload


def incidents_diff(before: dict[str, Any], after: dict[str, Any]) -> list[dict[str, str]]:
    changes = []
    keys = set(before) | set(after)
    for name in sorted(keys):
        left = str(before.get(name) or '')
        right = str(after.get(name) or '')
        if left != right:
            changes.append({'field': name, 'from': left, 'to': right})
    return changes


def incidents_related_status(rows: list[dict[str, Any]], status: str) -> list[dict[str, Any]]:
    return [row for row in rows if str(row.get('status') or '') == status]


def incidents_oldest(rows: list[dict[str, Any]], count: int = 5) -> list[dict[str, Any]]:
    ordered = incidents_sort_rows(rows, field='created_at', reverse=False)
    return ordered[:count]


def incidents_newest(rows: list[dict[str, Any]], count: int = 5) -> list[dict[str, Any]]:
    ordered = incidents_sort_rows(rows, field='created_at', reverse=True)
    return ordered[:count]


def incidents_attention_queue(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    queue = [row for row in rows if int(row.get('health_score') or 0) < 50]
    return incidents_sort_rows(queue, field='health_score', reverse=False)


def incidents_completeness(row: dict[str, Any]) -> int:
    filled = 0
    for name in INDEX_FIELDS:
        if str(row.get(name) or '').strip():
            filled += 1
    if not INDEX_FIELDS:
        return 0
    return int((filled / len(INDEX_FIELDS)) * 100)


def incidents_board(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'total': len(rows),
        'bands': incidents_health_bands(rows),
        'attention': len(incidents_attention_queue(rows)),
        'newest': incidents_newest(rows, 3),
        'oldest': incidents_oldest(rows, 3),
    }

def incidents_values_incident_no(rows: list[dict[str, Any]]) -> list[str]:
    """Distinct Incident No values used in Incident Room."""
    values = []
    seen: set[str] = set()
    for row in rows:
        item = str(row.get('incident_no') or '')
        if item and item not in seen:
            seen.add(item)
            values.append(item)
    return values


def incidents_filter_incident_no(rows: list[dict[str, Any]], expected: str) -> list[dict[str, Any]]:
    wanted = str(expected or '').strip()
    if not wanted:
        return list(rows)
    return [row for row in rows if str(row.get('incident_no') or '') == wanted]


def incidents_values_title(rows: list[dict[str, Any]]) -> list[str]:
    """Distinct Title values used in Incident Room."""
    values = []
    seen: set[str] = set()
    for row in rows:
        item = str(row.get('title') or '')
        if item and item not in seen:
            seen.add(item)
            values.append(item)
    return values


def incidents_filter_title(rows: list[dict[str, Any]], expected: str) -> list[dict[str, Any]]:
    wanted = str(expected or '').strip()
    if not wanted:
        return list(rows)
    return [row for row in rows if str(row.get('title') or '') == wanted]


def incidents_values_severity(rows: list[dict[str, Any]]) -> list[str]:
    """Distinct Severity values used in Incident Room."""
    values = []
    seen: set[str] = set()
    for row in rows:
        item = str(row.get('severity') or '')
        if item and item not in seen:
            seen.add(item)
            values.append(item)
    return values


def incidents_filter_severity(rows: list[dict[str, Any]], expected: str) -> list[dict[str, Any]]:
    wanted = str(expected or '').strip()
    if not wanted:
        return list(rows)
    return [row for row in rows if str(row.get('severity') or '') == wanted]


def incidents_values_commander(rows: list[dict[str, Any]]) -> list[str]:
    """Distinct Commander values used in Incident Room."""
    values = []
    seen: set[str] = set()
    for row in rows:
        item = str(row.get('commander') or '')
        if item and item not in seen:
            seen.add(item)
            values.append(item)
    return values


def incidents_filter_commander(rows: list[dict[str, Any]], expected: str) -> list[dict[str, Any]]:
    wanted = str(expected or '').strip()
    if not wanted:
        return list(rows)
    return [row for row in rows if str(row.get('commander') or '') == wanted]


def incidents_values_started_at(rows: list[dict[str, Any]]) -> list[str]:
    """Distinct Started At values used in Incident Room."""
    values = []
    seen: set[str] = set()
    for row in rows:
        item = str(row.get('started_at') or '')
        if item and item not in seen:
            seen.add(item)
            values.append(item)
    return values


def incidents_filter_started_at(rows: list[dict[str, Any]], expected: str) -> list[dict[str, Any]]:
    wanted = str(expected or '').strip()
    if not wanted:
        return list(rows)
    return [row for row in rows if str(row.get('started_at') or '') == wanted]


def incidents_values_status(rows: list[dict[str, Any]]) -> list[str]:
    """Distinct Status values used in Incident Room."""
    values = []
    seen: set[str] = set()
    for row in rows:
        item = str(row.get('status') or '')
        if item and item not in seen:
            seen.add(item)
            values.append(item)
    return values


def incidents_filter_status(rows: list[dict[str, Any]], expected: str) -> list[dict[str, Any]]:
    wanted = str(expected or '').strip()
    if not wanted:
        return list(rows)
    return [row for row in rows if str(row.get('status') or '') == wanted]


