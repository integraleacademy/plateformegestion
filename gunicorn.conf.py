def post_worker_init(worker):
    # Start after the fork, including when Gunicorn preloads the Flask app.
    import app as services
    services.jury_workflow.start(services.app, services)
