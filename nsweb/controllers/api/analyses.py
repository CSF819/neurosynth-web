from nsweb.controllers.api import bp
from flask import request, jsonify, url_for, abort, redirect
from nsweb.models.analyses import (TermAnalysis, AnalysisSet, CustomAnalysis,
                                   Analysis)
from nsweb.models.studies import Study
from nsweb.models.frequencies import Frequency
from nsweb.core import db
from flask_login import current_user
from flask_user import login_required
import datetime as dt
import json
import uuid


@bp.route('/terms/')
def list_terms():

    results_per_page = int(request.args['length'])
    offset = int(request.args['start'])

    order_by = '{0} {1}'.format(
        ['name', 'n_studies', 'n_activations'][
            int(request.args['order[0][column]'])],
        str(request.args['order[0][dir]']))
    search = str(request.args['search[value]']).strip()

    data = TermAnalysis.query
    if search:  # No empty search on my watch
        search = '%{}%'.format(search)
        data = data.filter(TermAnalysis.name.like(search))
    data = data.order_by(order_by)
    data = data.paginate(page=(offset / results_per_page) + 1,
                         per_page=results_per_page, error_out=False)
    result = {}
    result['draw'] = int(request.args['draw'])  # for security
    result['recordsTotal'] = TermAnalysis.query.count()
    result['recordsFiltered'] = data.total
    result['data'] = [
        ['<a href={0}>{1}</a>'.format(
            url_for('analyses.show_term', term=d.name), d.name),
         d.n_studies,
         d.n_activations,
         ] for d in data.items]
    result = jsonify(**result)
    return result


@bp.route('/topics/')
def list_topic_sets():
    topic_sets = AnalysisSet.query.filter_by(type='topics').all()
    data = [[
        '<a href={0}>{1}</a>'.format(
            url_for('analyses.show_topic_set', topic_set=ts.name),
            ts.name),
        ts.description,
        ts.n_analyses] for ts in topic_sets]
    return jsonify(data=data)


@bp.route('/topics/<string:topic_set>/')
def list_topics(topic_set):
    ts = AnalysisSet.query.filter_by(name=topic_set).first()
    data = [
        ['<a href={0}>{1}</a>'.format(
            url_for('analyses.show_topic', topic_set=ts.name,
                    number=t.number), 'Topic ' + str(t.number).zfill(3)),
         t.terms,
         t.n_studies
         ] for t in ts.analyses]
    return jsonify(data=data)


@bp.route('/analyses/<string:name>/')
def find_api_analysis(name):
    """ If the passed val isn't numeric, assume it's a analysis name,
    and retrieve the corresponding numeric ID.
    """
    val = Analysis.query.filter_by(name=name).first().id
    return redirect(url_for('analyses.api', id=val))


@bp.route('/analyses/<int:val>/')
def analyses_api(val):
    data = Analysis.query.get(val)
# data=Frequency.query.filter_by(analysis_id=int(val))#attempted
# optimization. Join causes slower performance however
    data = [['<a href={0}>{1}</a>'.format(url_for('studies.show', val=f.pmid),
                                          f.study.title),
             f.study.authors,
             f.study.journal,
             f.study.year,
             round(f.frequency, 3),
             ] for f in data.frequencies]
    data = jsonify(aaData=data)
    return data


@bp.route('/custom/save/', methods=['POST', 'GET'])
@login_required
def save_custom_analysis():
    """
    Expects a JSON string with the following schema:
      'data':
        'uuid': (optional) uuid of existing analysis to update
        'name': (optional) name of analysis
        'studies': List of PMIDs
    :return:
    """
    data = json.loads(request.form['data'])
    name = data.get('name')
    uid = data.get('uuid')
    studies = data.get('studies', [])
    description = data.get('description')
    private = data.get('private')
    pmids = [int(x) for x in studies]

    # Verify that all requested pmids are in the database
    for pmid in pmids:
        study = Study.query.filter_by(pmid=pmid).first()
        if not study:
            return jsonify(
                dict(result='error', error='Invalid PMID: %s' % pmid))

    if uid:
        custom_analysis = CustomAnalysis.query.filter_by(
            uuid=uid, user_id=current_user.id).first()
        if not custom_analysis:
            return jsonify(
                dict(result='error', error='No matching analysis found.'))
        if name:
            custom_analysis.name = name
        if description is not None:
            custom_analysis.description = description
        custom_analysis.private = private
    else:
        # create new custom analysis
        uid = str(uuid.uuid4())[:18]
        custom_analysis = CustomAnalysis(
            uuid=uid, name=name, description=description,
            user_id=current_user.id, private=private)
    # Explicitly update timestamp, because it won't be changed if only studies
    # are modified, and we need to compare this with last_run_at later.
    custom_analysis.updated_at = dt.datetime.utcnow()
    custom_analysis.n_studies = len(pmids)
    db.session.add(custom_analysis)
    db.session.commit()

    Frequency.query.filter_by(analysis_id=custom_analysis.id).delete()
    for pmid in pmids:
        freq = Frequency.query.filter_by(
            analysis_id=custom_analysis.id, pmid=pmid).first()
        if not freq:
            freq = Frequency(analysis_id=custom_analysis.id, pmid=pmid)
            db.session.add(freq)
    db.session.commit()

    return jsonify(dict(result='success', uuid=uid, id=custom_analysis.id))


@bp.route('/custom/<string:uid>/', methods=['GET'])
def get_custom_analysis(uid):
    """
    Given a uuid return JSON blob representing the custom analysis information
    and a list of its associated studies

    We're assuming that the user doesn't have to be logged in and that anyone
    can access the analysis if they know its uuid. This makes it easy for users
    to share links to their custom analyses.
    """
    custom = CustomAnalysis.query.filter_by(uuid=uid).first()
    if not custom:
        abort(404)
    if current_user.id != custom.user_id and (custom.private or not custom.last_run_at):
        abort(403)
    return jsonify(custom.serialize())

@bp.route('/custom/all/', methods=['GET'])
@login_required
def get_custom_analyses():
    """
    :return: All stored custom analyses for the requesting user
    """
    response = {
        'analyses': [custom.serialize() for custom in
                     CustomAnalysis.query.filter_by(user_id=current_user.id)]
    }
    return jsonify(response)


@bp.route('/custom/copy/<string:uid>/', methods=['POST'])
@login_required
def copy_custom_analysis(uid):
    """
    Given a uuid of an existing analysis, create a clone of the analysis with
    a new uuid
    :param uuid:
    :return: JSON blob including the new uuid
    """
    custom = CustomAnalysis.query.filter_by(uuid=uid).first()
    if not custom:
        abort(404)

    uid = str(uuid.uuid4())[:18]
    new_custom = CustomAnalysis(
        uuid=uid, user_id=current_user.id, name=custom.name)
    db.session.add(new_custom)
    db.session.commit()

    for freq in custom.frequencies.all():
        new_freq = Frequency(analysis_id=new_custom.id, pmid=freq.pmid)
        db.session.add(new_freq)
    db.session.commit()

    response = dict(uuid=uid, result="success")
    return jsonify(response)


@bp.route('/custom/<string:uid>/', methods=['DELETE'])
@login_required
def delete_custom_analysis(uid):
    """
    Given a uuid of an existing analysis, delete it.

    :param uuid:
    :return:
    """
    custom = CustomAnalysis.query.filter_by(uuid=uid).first()
    if not custom:
        abort(404)
    if custom.user_id != current_user.id:
        abort(403)
    # TODO: instead of deleting, consider setting a deleted flag instead
    db.session.delete(custom)
    db.session.commit()
    return jsonify(dict(result='success'))
