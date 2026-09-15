def register_blueprints(app):
    from .dashboard import bp as dashboard
    from .transactions import bp as transactions
    from .categories import bp as categories
    from .analytics import bp as analytics
    from .budgets import bp as budgets
    from .settings import bp as settings
    from .transfer import bp as transfer
    from .goals import bp as goals
    from .backups import bp as backups
    from .importing import bp as importing
    for blueprint in (dashboard, transactions, categories, analytics, budgets, settings, transfer, goals, backups, importing):
        app.register_blueprint(blueprint)
