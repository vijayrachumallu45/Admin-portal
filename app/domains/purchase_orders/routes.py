"""HTTP routes for Purchase Orders."""
from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for, Response

from app.security import login_required
from app.domains.purchase_orders.engine import DOMAIN_TITLE, STATUSES, engine, explain_purchase_orders_score

bp = Blueprint('purchase_orders', __name__, url_prefix='/purchase_orders')


@bp.get('/')
@login_required
def list_purchase_orders():
    filters = {'q': request.args.get('q', ''), 'status': request.args.get('status', '')}
    rows = engine.list_records(filters)
    kpis = engine.kpi_pack()
    return render_template(
        'purchase_orders/list.html',
        title=DOMAIN_TITLE,
        rows=rows,
        kpis=kpis,
        statuses=STATUSES,
        filters=filters,
        domain_key='purchase_orders',
    )


@bp.get('/new')
@login_required
def new_purchase_orders():
    return render_template(
        'purchase_orders/form.html',
        title='Create ' + DOMAIN_TITLE,
        record={},
        statuses=STATUSES,
        errors=[],
        domain_key='purchase_orders',
    )


@bp.post('/new')
@login_required
def create_purchase_orders():
    payload = request.form.to_dict()
    row, errors = engine.create(payload)
    if errors:
        return render_template(
            'purchase_orders/form.html',
            title='Create ' + DOMAIN_TITLE,
            record=payload,
            statuses=STATUSES,
            errors=errors,
            domain_key='purchase_orders',
        ), 400
    flash(DOMAIN_TITLE + ' record created', 'ok')
    return redirect(url_for('purchase_orders.detail_purchase_orders', record_id=row['id']))


@bp.get('/<record_id>')
@login_required
def detail_purchase_orders(record_id: str):
    row = engine.get(record_id)
    if row is None:
        flash('Record not found', 'error')
        return redirect(url_for('purchase_orders.list_purchase_orders'))
    notes = explain_purchase_orders_score(row)
    return render_template(
        'purchase_orders/detail.html',
        title=DOMAIN_TITLE,
        record=row,
        notes=notes,
        statuses=STATUSES,
        domain_key='purchase_orders',
    )


@bp.get('/<record_id>/edit')
@login_required
def edit_purchase_orders(record_id: str):
    row = engine.get(record_id)
    if row is None:
        flash('Record not found', 'error')
        return redirect(url_for('purchase_orders.list_purchase_orders'))
    return render_template(
        'purchase_orders/form.html',
        title='Edit ' + DOMAIN_TITLE,
        record=row,
        statuses=STATUSES,
        errors=[],
        domain_key='purchase_orders',
    )


@bp.post('/<record_id>/edit')
@login_required
def update_purchase_orders(record_id: str):
    payload = request.form.to_dict()
    row, errors = engine.update(record_id, payload)
    if errors:
        payload['id'] = record_id
        return render_template(
            'purchase_orders/form.html',
            title='Edit ' + DOMAIN_TITLE,
            record=payload,
            statuses=STATUSES,
            errors=errors,
            domain_key='purchase_orders',
        ), 400
    flash(DOMAIN_TITLE + ' record saved', 'ok')
    return redirect(url_for('purchase_orders.detail_purchase_orders', record_id=record_id))


@bp.post('/<record_id>/transition')
@login_required
def transition_purchase_orders(record_id: str):
    new_status = request.form.get('status', '')
    row, errors = engine.transition(record_id, new_status)
    if errors:
        flash(errors[0], 'error')
    else:
        flash('Status moved to ' + new_status, 'ok')
    return redirect(url_for('purchase_orders.detail_purchase_orders', record_id=record_id))


@bp.post('/<record_id>/delete')
@login_required
def delete_purchase_orders(record_id: str):
    engine.delete(record_id)
    flash('Record removed', 'ok')
    return redirect(url_for('purchase_orders.list_purchase_orders'))


@bp.get('/export.csv')
@login_required
def export_purchase_orders():
    table = engine.export_rows()
    lines = [','.join(cell.replace(',', ' ') for cell in row) for row in table]
    body = '\n'.join(lines) + '\n'
    return Response(
        body,
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=purchase_orders.csv'},
    )


@bp.get('/report')
@login_required
def report_purchase_orders():
    aging = engine.aging_report()
    kpis = engine.kpi_pack()
    return render_template(
        'purchase_orders/report.html',
        title=DOMAIN_TITLE + ' report',
        aging=aging,
        kpis=kpis,
        domain_key='purchase_orders',
    )

