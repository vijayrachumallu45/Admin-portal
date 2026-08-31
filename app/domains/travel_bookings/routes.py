"""HTTP routes for Travel Bookings."""
from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for, Response

from app.security import login_required
from app.domains.travel_bookings.engine import DOMAIN_TITLE, STATUSES, engine, explain_travel_bookings_score

bp = Blueprint('travel_bookings', __name__, url_prefix='/travel_bookings')


@bp.get('/')
@login_required
def list_travel_bookings():
    filters = {'q': request.args.get('q', ''), 'status': request.args.get('status', '')}
    rows = engine.list_records(filters)
    kpis = engine.kpi_pack()
    return render_template(
        'travel_bookings/list.html',
        title=DOMAIN_TITLE,
        rows=rows,
        kpis=kpis,
        statuses=STATUSES,
        filters=filters,
        domain_key='travel_bookings',
    )


@bp.get('/new')
@login_required
def new_travel_bookings():
    return render_template(
        'travel_bookings/form.html',
        title='Create ' + DOMAIN_TITLE,
        record={},
        statuses=STATUSES,
        errors=[],
        domain_key='travel_bookings',
    )


@bp.post('/new')
@login_required
def create_travel_bookings():
    payload = request.form.to_dict()
    row, errors = engine.create(payload)
    if errors:
        return render_template(
            'travel_bookings/form.html',
            title='Create ' + DOMAIN_TITLE,
            record=payload,
            statuses=STATUSES,
            errors=errors,
            domain_key='travel_bookings',
        ), 400
    flash(DOMAIN_TITLE + ' record created', 'ok')
    return redirect(url_for('travel_bookings.detail_travel_bookings', record_id=row['id']))


@bp.get('/<record_id>')
@login_required
def detail_travel_bookings(record_id: str):
    row = engine.get(record_id)
    if row is None:
        flash('Record not found', 'error')
        return redirect(url_for('travel_bookings.list_travel_bookings'))
    notes = explain_travel_bookings_score(row)
    return render_template(
        'travel_bookings/detail.html',
        title=DOMAIN_TITLE,
        record=row,
        notes=notes,
        statuses=STATUSES,
        domain_key='travel_bookings',
    )


@bp.get('/<record_id>/edit')
@login_required
def edit_travel_bookings(record_id: str):
    row = engine.get(record_id)
    if row is None:
        flash('Record not found', 'error')
        return redirect(url_for('travel_bookings.list_travel_bookings'))
    return render_template(
        'travel_bookings/form.html',
        title='Edit ' + DOMAIN_TITLE,
        record=row,
        statuses=STATUSES,
        errors=[],
        domain_key='travel_bookings',
    )


@bp.post('/<record_id>/edit')
@login_required
def update_travel_bookings(record_id: str):
    payload = request.form.to_dict()
    row, errors = engine.update(record_id, payload)
    if errors:
        payload['id'] = record_id
        return render_template(
            'travel_bookings/form.html',
            title='Edit ' + DOMAIN_TITLE,
            record=payload,
            statuses=STATUSES,
            errors=errors,
            domain_key='travel_bookings',
        ), 400
    flash(DOMAIN_TITLE + ' record saved', 'ok')
    return redirect(url_for('travel_bookings.detail_travel_bookings', record_id=record_id))


@bp.post('/<record_id>/transition')
@login_required
def transition_travel_bookings(record_id: str):
    new_status = request.form.get('status', '')
    row, errors = engine.transition(record_id, new_status)
    if errors:
        flash(errors[0], 'error')
    else:
        flash('Status moved to ' + new_status, 'ok')
    return redirect(url_for('travel_bookings.detail_travel_bookings', record_id=record_id))


@bp.post('/<record_id>/delete')
@login_required
def delete_travel_bookings(record_id: str):
    engine.delete(record_id)
    flash('Record removed', 'ok')
    return redirect(url_for('travel_bookings.list_travel_bookings'))


@bp.get('/export.csv')
@login_required
def export_travel_bookings():
    table = engine.export_rows()
    lines = [','.join(cell.replace(',', ' ') for cell in row) for row in table]
    body = '\n'.join(lines) + '\n'
    return Response(
        body,
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=travel_bookings.csv'},
    )


@bp.get('/report')
@login_required
def report_travel_bookings():
    aging = engine.aging_report()
    kpis = engine.kpi_pack()
    return render_template(
        'travel_bookings/report.html',
        title=DOMAIN_TITLE + ' report',
        aging=aging,
        kpis=kpis,
        domain_key='travel_bookings',
    )

