"""Blueprint registration."""


def register_blueprints(app) -> None:
    from .auth import bp as auth_bp
    from .dashboard import bp as dashboard_bp
    from .exercises import bp as exercises_bp
    from .logbook import bp as logbook_bp
    from .pwa import bp as pwa_bp
    from .programs import bp as programs_bp
    from .records import bp as records_bp
    from .settings import bp as settings_bp
    from .stats import bp as stats_bp
    from .workouts import bp as workouts_bp
    from .api import bp as api_bp

    for blueprint in (
        auth_bp,
        pwa_bp,
        dashboard_bp,
        programs_bp,
        exercises_bp,
        workouts_bp,
        logbook_bp,
        stats_bp,
        records_bp,
        settings_bp,
        api_bp,
    ):
        app.register_blueprint(blueprint)
