def post_worker_init(worker):
    # Start after the fork, including when Gunicorn preloads the Flask app.
    import app as services
    from services import published_schedule_import
    published_schedule_import.start(services)
    services.jury_workflow.start(services.app, services)
