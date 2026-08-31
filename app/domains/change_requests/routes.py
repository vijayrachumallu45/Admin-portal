"""HTTP routes for Change Requests."""
from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for, Response

from app.security import login_required
from app.domains.change_requests.engine import DOMAIN_TITLE, STATUSES, engine, explain_change_requests_score

bp = Blueprint('change_requests', __name__, url_prefix='/change_requests')


@bp.get('/')
@login_required
def list_change_requests():
    filters = {'q': request.args.get('q', ''), 'status': request.args.get('status', '')}
    rows = engine.list_records(filters)
    kpis = engine.kpi_pack()
    return render_template(
        'change_requests/list.html',
        title=DOMAIN_TITLE,
        rows=rows,
        kpis=kpis,
        statuses=STATUSES,
        filters=filters,
        domain_key='change_requests',
    )


@bp.get('/new')
@login_required
def new_change_requests():
    return render_template(
        'change_requests/form.html',
        title='Create ' + DOMAIN_TITLE,
        record={},
        statuses=STATUSES,
        errors=[],
        domain_key='change_requests',
    )


@bp.post('/new')
@login_required
def create_change_requests():
    payload = request.form.to_dict()
    row, errors = engine.create(payload)
    if errors:
        return render_template(
            'change_requests/form.html',
            title='Create ' + DOMAIN_TITLE,
            record=payload,
            statuses=STATUSES,
            errors=errors,
            domain_key='change_requests',
        ), 400
    flash(DOMAIN_TITLE + ' record created', 'ok')
    return redirect(url_for('change_requests.detail_change_requests', record_id=row['id']))


@bp.get('/<record_id>')
@login_required
def detail_change_requests(record_id: str):
    row = engine.get(record_id)
    if row is None:
        flash('Record not found', 'error')
        return redirect(url_for('change_requests.list_change_requests'))
    notes = explain_change_requests_score(row)
    return render_template(
        'change_requests/detail.html',
        title=DOMAIN_TITLE,
        record=row,
        notes=notes,
        statuses=STATUSES,
        domain_key='change_requests',
    )


@bp.get('/<record_id>/edit')
@login_required
def edit_change_requests(record_id: str):
    row = engine.get(record_id)
    if row is None:
        flash('Record not found', 'error')
        return redirect(url_for('change_requests.list_change_requests'))
    return render_template(
        'change_requests/form.html',
        title='Edit ' + DOMAIN_TITLE,
        record=row,
        statuses=STATUSES,
        errors=[],
        domain_key='change_requests',
    )


@bp.post('/<record_id>/edit')
@login_required
def update_change_requests(record_id: str):
    payload = request.form.to_dict()
    row, errors = engine.update(record_id, payload)
    if errors:
        payload['id'] = record_id
        return render_template(
            'change_requests/form.html',
            title='Edit ' + DOMAIN_TITLE,
            record=payload,
            statuses=STATUSES,
            errors=errors,
            domain_key='change_requests',
        ), 400
    flash(DOMAIN_TITLE + ' record saved', 'ok')
    return redirect(url_for('change_requests.detail_change_requests', record_id=record_id))


@bp.post('/<record_id>/transition')
@login_required
def transition_change_requests(record_id: str):
    new_status = request.form.get('status', '')
    row, errors = engine.transition(record_id, new_status)
    if errors:
        flash(errors[0], 'error')
    else:
        flash('Status moved to ' + new_status, 'ok')
    return redirect(url_for('change_requests.detail_change_requests', record_id=record_id))


@bp.post('/<record_id>/delete')
@login_required
def delete_change_requests(record_id: str):
    engine.delete(record_id)
    flash('Record removed', 'ok')
    return redirect(url_for('change_requests.list_change_requests'))


@bp.get('/export.csv')
@login_required
def export_change_requests():
    table = engine.export_rows()
    lines = [','.join(cell.replace(',', ' ') for cell in row) for row in table]
    body = '\n'.join(lines) + '\n'
    return Response(
        body,
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=change_requests.csv'},
    )


@bp.get('/report')
@login_required
def report_change_requests():
    aging = engine.aging_report()
    kpis = engine.kpi_pack()
    return render_template(
        'change_requests/report.html',
        title=DOMAIN_TITLE + ' report',
        aging=aging,
        kpis=kpis,
        domain_key='change_requests',
    )

