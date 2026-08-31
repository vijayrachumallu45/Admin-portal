"""HTTP routes for Price Books."""
from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for, Response

from app.security import login_required
from app.domains.price_books.engine import DOMAIN_TITLE, STATUSES, engine, explain_price_books_score

bp = Blueprint('price_books', __name__, url_prefix='/price_books')


@bp.get('/')
@login_required
def list_price_books():
    filters = {'q': request.args.get('q', ''), 'status': request.args.get('status', '')}
    rows = engine.list_records(filters)
    kpis = engine.kpi_pack()
    return render_template(
        'price_books/list.html',
        title=DOMAIN_TITLE,
        rows=rows,
        kpis=kpis,
        statuses=STATUSES,
        filters=filters,
        domain_key='price_books',
    )


@bp.get('/new')
@login_required
def new_price_books():
    return render_template(
        'price_books/form.html',
        title='Create ' + DOMAIN_TITLE,
        record={},
        statuses=STATUSES,
        errors=[],
        domain_key='price_books',
    )


@bp.post('/new')
@login_required
def create_price_books():
    payload = request.form.to_dict()
    row, errors = engine.create(payload)
    if errors:
        return render_template(
            'price_books/form.html',
            title='Create ' + DOMAIN_TITLE,
            record=payload,
            statuses=STATUSES,
            errors=errors,
            domain_key='price_books',
        ), 400
    flash(DOMAIN_TITLE + ' record created', 'ok')
    return redirect(url_for('price_books.detail_price_books', record_id=row['id']))


@bp.get('/<record_id>')
@login_required
def detail_price_books(record_id: str):
    row = engine.get(record_id)
    if row is None:
        flash('Record not found', 'error')
        return redirect(url_for('price_books.list_price_books'))
    notes = explain_price_books_score(row)
    return render_template(
        'price_books/detail.html',
        title=DOMAIN_TITLE,
        record=row,
        notes=notes,
        statuses=STATUSES,
        domain_key='price_books',
    )


@bp.get('/<record_id>/edit')
@login_required
def edit_price_books(record_id: str):
    row = engine.get(record_id)
    if row is None:
        flash('Record not found', 'error')
        return redirect(url_for('price_books.list_price_books'))
    return render_template(
        'price_books/form.html',
        title='Edit ' + DOMAIN_TITLE,
        record=row,
        statuses=STATUSES,
        errors=[],
        domain_key='price_books',
    )


@bp.post('/<record_id>/edit')
@login_required
def update_price_books(record_id: str):
    payload = request.form.to_dict()
    row, errors = engine.update(record_id, payload)
    if errors:
        payload['id'] = record_id
        return render_template(
            'price_books/form.html',
            title='Edit ' + DOMAIN_TITLE,
            record=payload,
            statuses=STATUSES,
            errors=errors,
            domain_key='price_books',
        ), 400
    flash(DOMAIN_TITLE + ' record saved', 'ok')
    return redirect(url_for('price_books.detail_price_books', record_id=record_id))


@bp.post('/<record_id>/transition')
@login_required
def transition_price_books(record_id: str):
    new_status = request.form.get('status', '')
    row, errors = engine.transition(record_id, new_status)
    if errors:
        flash(errors[0], 'error')
    else:
        flash('Status moved to ' + new_status, 'ok')
    return redirect(url_for('price_books.detail_price_books', record_id=record_id))


@bp.post('/<record_id>/delete')
@login_required
def delete_price_books(record_id: str):
    engine.delete(record_id)
    flash('Record removed', 'ok')
    return redirect(url_for('price_books.list_price_books'))


@bp.get('/export.csv')
@login_required
def export_price_books():
    table = engine.export_rows()
    lines = [','.join(cell.replace(',', ' ') for cell in row) for row in table]
    body = '\n'.join(lines) + '\n'
    return Response(
        body,
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=price_books.csv'},
    )


@bp.get('/report')
@login_required
def report_price_books():
    aging = engine.aging_report()
    kpis = engine.kpi_pack()
    return render_template(
        'price_books/report.html',
        title=DOMAIN_TITLE + ' report',
        aging=aging,
        kpis=kpis,
        domain_key='price_books',
    )

