from nsweb.core import apimanager, add_blueprint
from nsweb.models import Study
from flask import Blueprint, render_template, request

studies = Blueprint('studies', __name__, 
	url_prefix='/studies')

@studies.route('/')
def index():
	return render_template('studies/index.html', studies=Study.query.all())

@studies.route('/<id>')
def show(id):
	return render_template('studies/show.html', study=Study.query.get_or_404(id))

add_blueprint(studies)


# Begin API stuff
def update_result(result, **kwargs):
	""" Rename frequency to feature in JSON. 
	Note: this makes the JSON look nice when requests come in at
	/studies/3000, but breaks the native functionality when requests 
	come in at /studies/3000/frequencies.
	"""
	if 'frequencies' in result:
		result['features'] = result.pop('frequencies')
		for f in result['features']:
			f['frequency'] = round(f['frequency'], 3)
		pass

def datatables_postprocessor(result, **kwargs):
	""" A wrapper for DataTables requests. Just takes the JSON object to be 
	returned and adds the fields DataTables is expecting. This should probably be 
	made a universal postprocessor and applied to all API requests that have a 
	'datatables' key in the request arguments list. """
	if 'datatables' in request.args:
		result['iTotalRecords'] = 9999  # Get the number of total records from DB
		result['iTotalDisplayRecords'] = result.pop('num_results')
		result['aaData'] = result.pop('objects')
		result['sEcho'] = int(request.args['sEcho'])  # for security
		# ...and so on for anything else we need

def datatables_preprocessor(search_params=None, **kwargs):
	""" For DataTables AJAX requests, we may need to change the search params. 
	"""
	print search_params
	# if 'datatables' in request.args:
	# 	# Add any filters we need...
	# 	search_params = {
	# 		'filters': {}
	# 	}
	# 	# Convert the DataTables query parameters into what flask-restless wants
	# 	if 'iDisplayStart' in request.args:

		

includes=['pmid',
		'title',
		'authors',
		'journal',
		'year',
		'peaks',
		'peaks.x',
		'peaks.y',
		'peaks.z',
		# 'frequencies',
		# 'frequencies.frequency',
		# 'frequencies.feature_id',
		'features',
		'features.feature'
		]
add_blueprint(apimanager.create_api_blueprint(Study,
                                              methods=['GET'],
                                              collection_name='studies',
                                              results_per_page=20,
                                              max_results_per_page=100,
                                              include_columns=includes,
                                              postprocessors={
                                              	'GET_SINGLE': [update_result],
                                              	'GET_MANY': [datatables_postprocessor]
                                              },
                                              preprocessors={
                                              	'GET_MANY': [datatables_preprocessor]
                                              }))
