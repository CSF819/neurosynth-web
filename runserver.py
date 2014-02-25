import nsweb.core
from nsweb import settings
from nsweb.core import setup_logging, create_app

(app,db,manager) = create_app(database_uri = settings.SQLALCHEMY_DATABASE_URI, debug=True)#,debug=settings.DEBUG, aptana=True)
import nsweb.studies.studies
import nsweb.features.features
setup_logging(logging_path=settings.LOGGING_PATH,level=settings.LOGGING_LEVEL)
app.run()

if __name__ == "__main__":
    # To allow aptana to receive errors, set use_debugger=False
    if app.debug: use_debugger = False
    try:
        # Disable Flask's debugger if external debugger is requested
        use_debugger = not(app.config.get('DEBUG_WITH_APTANA'))
    except:
        pass
    app.run(use_debugger=use_debugger, debug=app.debug,
            use_reloader=use_debugger, host='127.0.0.1')