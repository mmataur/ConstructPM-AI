from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


def session_factory(url):
    return sessionmaker(create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=5), expire_on_commit=False)


def set_context(db, actor, organization="", email="", invite=""):
    # Transaction-local: pooled connections cannot retain another request's scope.
    for key, value in {"actor": actor, "tenant": organization, "email": email, "invite": invite}.items():
        db.execute(text("SELECT set_config(:key, :value, true)"), {"key": f"app.{key}", "value": value})

