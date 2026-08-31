"""HTTP routes for Product Catalog."""
from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for, Response

from app.security import login_required
from app.domains.catalog_products.engine import DOMAIN_TITLE, STATUSES, engine, explain_catalog_products_score

bp = Blueprint('catalog_products', __name__, url_prefix='/catalog_products')


@bp.get('/')
@login_required
def list_catalog_products():
    filters = {'q': request.args.get('q', ''), 'status': request.args.get('status', '')}
    rows = engine.list_records(filters)
    kpis = engine.kpi_pack()
    return render_template(
        'catalog_products/list.html',
        title=DOMAIN_TITLE,
        rows=rows,
        kpis=kpis,
        statuses=STATUSES,
        filters=filters,
        domain_key='catalog_products',
    )


@bp.get('/new')
@login_required
def new_catalog_products():
    return render_template(
        'catalog_products/form.html',
        title='Create ' + DOMAIN_TITLE,
        record={},
        statuses=STATUSES,
        errors=[],
        domain_key='catalog_products',
    )


@bp.post('/new')
@login_required
def create_catalog_products():
    payload = request.form.to_dict()
    row, errors = engine.create(payload)
    if errors:
        return render_template(
            'catalog_products/form.html',
            title='Create ' + DOMAIN_TITLE,
            record=payload,
            statuses=STATUSES,
            errors=errors,
            domain_key='catalog_products',
        ), 400
    flash(DOMAIN_TITLE + ' record created', 'ok')
    return redirect(url_for('catalog_products.detail_catalog_products', record_id=row['id']))


@bp.get('/<record_id>')
@login_required
def detail_catalog_products(record_id: str):
    row = engine.get(record_id)
    if row is None:
        flash('Record not found', 'error')
        return redirect(url_for('catalog_products.list_catalog_products'))
    notes = explain_catalog_products_score(row)
    return render_template(
        'catalog_products/detail.html',
        title=DOMAIN_TITLE,
        record=row,
        notes=notes,
        statuses=STATUSES,
        domain_key='catalog_products',
    )


@bp.get('/<record_id>/edit')
@login_required
def edit_catalog_products(record_id: str):
    row = engine.get(record_id)
    if row is None:
        flash('Record not found', 'error')
        return redirect(url_for('catalog_products.list_catalog_products'))
    return render_template(
        'catalog_products/form.html',
        title='Edit ' + DOMAIN_TITLE,
        record=row,
        statuses=STATUSES,
        errors=[],
        domain_key='catalog_products',
    )


@bp.post('/<record_id>/edit')
@login_required
def update_catalog_products(record_id: str):
    payload = request.form.to_dict()
    row, errors = engine.update(record_id, payload)
    if errors:
        payload['id'] = record_id
        return render_template(
            'catalog_products/form.html',
            title='Edit ' + DOMAIN_TITLE,
            record=payload,
            statuses=STATUSES,
            errors=errors,
            domain_key='catalog_products',
        ), 400
    flash(DOMAIN_TITLE + ' record saved', 'ok')
    return redirect(url_for('catalog_products.detail_catalog_products', record_id=record_id))


@bp.post('/<record_id>/transition')
@login_required
def transition_catalog_products(record_id: str):
    new_status = request.form.get('status', '')
    row, errors = engine.transition(record_id, new_status)
    if errors:
        flash(errors[0], 'error')
    else:
        flash('Status moved to ' + new_status, 'ok')
    return redirect(url_for('catalog_products.detail_catalog_products', record_id=record_id))


@bp.post('/<record_id>/delete')
@login_required
def delete_catalog_products(record_id: str):
    engine.delete(record_id)
    flash('Record removed', 'ok')
    return redirect(url_for('catalog_products.list_catalog_products'))


@bp.get('/export.csv')
@login_required
def export_catalog_products():
    table = engine.export_rows()
    lines = [','.join(cell.replace(',', ' ') for cell in row) for row in table]
    body = '\n'.join(lines) + '\n'
    return Response(
        body,
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=catalog_products.csv'},
    )


@bp.get('/report')
@login_required
def report_catalog_products():
    aging = engine.aging_report()
    kpis = engine.kpi_pack()
    return render_template(
        'catalog_products/report.html',
        title=DOMAIN_TITLE + ' report',
        aging=aging,
        kpis=kpis,
        domain_key='catalog_products',
    )

