"""HTTP routes for Data Catalog."""
from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for, Response

from app.security import login_required
from app.domains.data_assets.engine import DOMAIN_TITLE, STATUSES, engine, explain_data_assets_score

bp = Blueprint('data_assets', __name__, url_prefix='/data_assets')


@bp.get('/')
@login_required
def list_data_assets():
    filters = {'q': request.args.get('q', ''), 'status': request.args.get('status', '')}
    rows = engine.list_records(filters)
    kpis = engine.kpi_pack()
    return render_template(
        'data_assets/list.html',
        title=DOMAIN_TITLE,
        rows=rows,
        kpis=kpis,
        statuses=STATUSES,
        filters=filters,
        domain_key='data_assets',
    )


@bp.get('/new')
@login_required
def new_data_assets():
    return render_template(
        'data_assets/form.html',
        title='Create ' + DOMAIN_TITLE,
        record={},
        statuses=STATUSES,
        errors=[],
        domain_key='data_assets',
    )


@bp.post('/new')
@login_required
def create_data_assets():
    payload = request.form.to_dict()
    row, errors = engine.create(payload)
    if errors:
        return render_template(
            'data_assets/form.html',
            title='Create ' + DOMAIN_TITLE,
            record=payload,
            statuses=STATUSES,
            errors=errors,
            domain_key='data_assets',
        ), 400
    flash(DOMAIN_TITLE + ' record created', 'ok')
    return redirect(url_for('data_assets.detail_data_assets', record_id=row['id']))


@bp.get('/<record_id>')
@login_required
def detail_data_assets(record_id: str):
    row = engine.get(record_id)
    if row is None:
        flash('Record not found', 'error')
        return redirect(url_for('data_assets.list_data_assets'))
    notes = explain_data_assets_score(row)
    return render_template(
        'data_assets/detail.html',
        title=DOMAIN_TITLE,
        record=row,
        notes=notes,
        statuses=STATUSES,
        domain_key='data_assets',
    )


@bp.get('/<record_id>/edit')
@login_required
def edit_data_assets(record_id: str):
    row = engine.get(record_id)
    if row is None:
        flash('Record not found', 'error')
        return redirect(url_for('data_assets.list_data_assets'))
    return render_template(
        'data_assets/form.html',
        title='Edit ' + DOMAIN_TITLE,
        record=row,
        statuses=STATUSES,
        errors=[],
        domain_key='data_assets',
    )


@bp.post('/<record_id>/edit')
@login_required
def update_data_assets(record_id: str):
    payload = request.form.to_dict()
    row, errors = engine.update(record_id, payload)
    if errors:
        payload['id'] = record_id
        return render_template(
            'data_assets/form.html',
            title='Edit ' + DOMAIN_TITLE,
            record=payload,
            statuses=STATUSES,
            errors=errors,
            domain_key='data_assets',
        ), 400
    flash(DOMAIN_TITLE + ' record saved', 'ok')
    return redirect(url_for('data_assets.detail_data_assets', record_id=record_id))


@bp.post('/<record_id>/transition')
@login_required
def transition_data_assets(record_id: str):
    new_status = request.form.get('status', '')
    row, errors = engine.transition(record_id, new_status)
    if errors:
        flash(errors[0], 'error')
    else:
        flash('Status moved to ' + new_status, 'ok')
    return redirect(url_for('data_assets.detail_data_assets', record_id=record_id))


@bp.post('/<record_id>/delete')
@login_required
def delete_data_assets(record_id: str):
    engine.delete(record_id)
    flash('Record removed', 'ok')
    return redirect(url_for('data_assets.list_data_assets'))


@bp.get('/export.csv')
@login_required
def export_data_assets():
    table = engine.export_rows()
    lines = [','.join(cell.replace(',', ' ') for cell in row) for row in table]
    body = '\n'.join(lines) + '\n'
    return Response(
        body,
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=data_assets.csv'},
    )


@bp.get('/report')
@login_required
def report_data_assets():
    aging = engine.aging_report()
    kpis = engine.kpi_pack()
    return render_template(
        'data_assets/report.html',
        title=DOMAIN_TITLE + ' report',
        aging=aging,
        kpis=kpis,
        domain_key='data_assets',
    )

