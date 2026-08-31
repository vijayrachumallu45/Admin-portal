"""HTTP routes for Feature Flags."""
from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for, Response

from app.security import login_required
from app.domains.feature_flags.engine import DOMAIN_TITLE, STATUSES, engine, explain_feature_flags_score

bp = Blueprint('feature_flags', __name__, url_prefix='/feature_flags')


@bp.get('/')
@login_required
def list_feature_flags():
    filters = {'q': request.args.get('q', ''), 'status': request.args.get('status', '')}
    rows = engine.list_records(filters)
    kpis = engine.kpi_pack()
    return render_template(
        'feature_flags/list.html',
        title=DOMAIN_TITLE,
        rows=rows,
        kpis=kpis,
        statuses=STATUSES,
        filters=filters,
        domain_key='feature_flags',
    )


@bp.get('/new')
@login_required
def new_feature_flags():
    return render_template(
        'feature_flags/form.html',
        title='Create ' + DOMAIN_TITLE,
        record={},
        statuses=STATUSES,
        errors=[],
        domain_key='feature_flags',
    )


@bp.post('/new')
@login_required
def create_feature_flags():
    payload = request.form.to_dict()
    row, errors = engine.create(payload)
    if errors:
        return render_template(
            'feature_flags/form.html',
            title='Create ' + DOMAIN_TITLE,
            record=payload,
            statuses=STATUSES,
            errors=errors,
            domain_key='feature_flags',
        ), 400
    flash(DOMAIN_TITLE + ' record created', 'ok')
    return redirect(url_for('feature_flags.detail_feature_flags', record_id=row['id']))


@bp.get('/<record_id>')
@login_required
def detail_feature_flags(record_id: str):
    row = engine.get(record_id)
    if row is None:
        flash('Record not found', 'error')
        return redirect(url_for('feature_flags.list_feature_flags'))
    notes = explain_feature_flags_score(row)
    return render_template(
        'feature_flags/detail.html',
        title=DOMAIN_TITLE,
        record=row,
        notes=notes,
        statuses=STATUSES,
        domain_key='feature_flags',
    )


@bp.get('/<record_id>/edit')
@login_required
def edit_feature_flags(record_id: str):
    row = engine.get(record_id)
    if row is None:
        flash('Record not found', 'error')
        return redirect(url_for('feature_flags.list_feature_flags'))
    return render_template(
        'feature_flags/form.html',
        title='Edit ' + DOMAIN_TITLE,
        record=row,
        statuses=STATUSES,
        errors=[],
        domain_key='feature_flags',
    )


@bp.post('/<record_id>/edit')
@login_required
def update_feature_flags(record_id: str):
    payload = request.form.to_dict()
    row, errors = engine.update(record_id, payload)
    if errors:
        payload['id'] = record_id
        return render_template(
            'feature_flags/form.html',
            title='Edit ' + DOMAIN_TITLE,
            record=payload,
            statuses=STATUSES,
            errors=errors,
            domain_key='feature_flags',
        ), 400
    flash(DOMAIN_TITLE + ' record saved', 'ok')
    return redirect(url_for('feature_flags.detail_feature_flags', record_id=record_id))


@bp.post('/<record_id>/transition')
@login_required
def transition_feature_flags(record_id: str):
    new_status = request.form.get('status', '')
    row, errors = engine.transition(record_id, new_status)
    if errors:
        flash(errors[0], 'error')
    else:
        flash('Status moved to ' + new_status, 'ok')
    return redirect(url_for('feature_flags.detail_feature_flags', record_id=record_id))


@bp.post('/<record_id>/delete')
@login_required
def delete_feature_flags(record_id: str):
    engine.delete(record_id)
    flash('Record removed', 'ok')
    return redirect(url_for('feature_flags.list_feature_flags'))


@bp.get('/export.csv')
@login_required
def export_feature_flags():
    table = engine.export_rows()
    lines = [','.join(cell.replace(',', ' ') for cell in row) for row in table]
    body = '\n'.join(lines) + '\n'
    return Response(
        body,
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=feature_flags.csv'},
    )


@bp.get('/report')
@login_required
def report_feature_flags():
    aging = engine.aging_report()
    kpis = engine.kpi_pack()
    return render_template(
        'feature_flags/report.html',
        title=DOMAIN_TITLE + ' report',
        aging=aging,
        kpis=kpis,
        domain_key='feature_flags',
    )

