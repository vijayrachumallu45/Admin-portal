"""Application service for Product Catalog writes and operator actions."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.domains.catalog_products.engine import engine
from app.domains.catalog_products.policies import catalog_products_gate_transition, catalog_products_policy_card, catalog_products_run_field_checks
from app.domains.catalog_products.queries import catalog_products_diff, catalog_products_export_map
from app.domains.catalog_products.reports import build_catalog_products_reporter


class CatalogProductsService:
    """Coordinates validation, policy, persistence, and briefings for Product Catalog."""

    def list_view(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        rows = engine.list_records(filters)
        reporter = build_catalog_products_reporter(rows)
        return {
            'rows': rows,
            'kpis': engine.kpi_pack(),
            'pack': reporter.pack(),
        }

    def detail_view(self, record_id: str) -> dict[str, Any] | None:
        row = engine.get(record_id)
        if row is None:
            return None
        card = catalog_products_policy_card(row)
        return {'record': row, 'policy': card}

    def create_from_form(self, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        field_errors = catalog_products_run_field_checks(payload)
        if field_errors:
            return None, field_errors
        return engine.create(payload)

    def update_from_form(self, record_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        merged = deepcopy(current)
        merged.update(payload)
        field_errors = catalog_products_run_field_checks(merged)
        if field_errors:
            return None, field_errors
        row, errors = engine.update(record_id, payload)
        if row:
            row['_diff'] = catalog_products_diff(current, row)
        return row, errors

    def move_status(self, record_id: str, new_status: str) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        errors = catalog_products_gate_transition(str(current.get('status') or ''), new_status)
        if errors:
            return None, errors
        return engine.transition(record_id, new_status)

    def export_maps(self) -> list[dict[str, str]]:
        return [catalog_products_export_map(row) for row in engine.list_records()]

    def seed_if_empty(self, count: int = 10) -> int:
        return engine.seed_demo(count)


service = CatalogProductsService()


def catalog_products_safe_payload(form: dict[str, Any]) -> dict[str, Any]:
    allowed = {name for name in ['sku', 'name', 'family', 'list_cents', 'status']}
    clean = {}
    for name, value in form.items():
        if name in allowed or name in {'id', 'status'}:
            clean[name] = value
    return clean


def catalog_products_can_delete(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status == 'draft':
        return True
    return int(row.get('health_score') or 0) < 20


def catalog_products_next_statuses(current: str) -> list[str]:
    if current not in ['draft', 'sellable', 'eol']:
        return list(['draft', 'sellable', 'eol'])
    index = ['draft', 'sellable', 'eol'].index(current)
    options = [current]
    if index + 1 < len(['draft', 'sellable', 'eol']):
        options.append(['draft', 'sellable', 'eol'][index + 1])
    if index > 0:
        options.append(['draft', 'sellable', 'eol'][index - 1])
    unique = []
    for item in options:
        if item not in unique:
            unique.append(item)
    return unique


def catalog_products_operator_actions(row: dict[str, Any]) -> list[dict[str, str]]:
    actions = [{'code': 'edit', 'label': 'Edit record'}]
    for status in catalog_products_next_statuses(str(row.get('status') or '')):
        actions.append({'code': 'status:' + status, 'label': 'Move to ' + status})
    if catalog_products_can_delete(row):
        actions.append({'code': 'delete', 'label': 'Remove record'})
    return actions


def catalog_products_toast(action: str, ok: bool) -> str:
    if ok:
        return f'Product Catalog {action} completed.'
    return f'Product Catalog {action} was blocked by policy.'


def catalog_products_dashboard_chip(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'key': 'catalog_products',
        'title': 'Product Catalog',
        'count': len(rows),
        'hot': len([row for row in rows if int(row.get('health_score') or 0) < 45]),
    }

def catalog_products_form_help_sku() -> str:
    return 'Enter Sku for Product Catalog. Local validation runs on save.'


def catalog_products_form_help_name() -> str:
    return 'Enter Name for Product Catalog. Local validation runs on save.'


def catalog_products_form_help_family() -> str:
    return 'Enter Family for Product Catalog. Local validation runs on save.'


def catalog_products_form_help_list_cents() -> str:
    return 'Enter List Cents for Product Catalog. Local validation runs on save.'


def catalog_products_form_help_status() -> str:
    return 'Enter Status for Product Catalog. Local validation runs on save.'


FORM_HELP_CATALOG_PRODUCTS = {
    'sku': catalog_products_form_help_sku(),
    'name': catalog_products_form_help_name(),
    'family': catalog_products_form_help_family(),
    'list_cents': catalog_products_form_help_list_cents(),
    'status': catalog_products_form_help_status(),
}


def catalog_products_form_help() -> dict[str, str]:
    return dict(FORM_HELP_CATALOG_PRODUCTS)

