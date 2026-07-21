import os

import sentry_sdk
from dotenv import load_dotenv
from flask import Flask
from flask_cors import CORS
from sentry_sdk.integrations.flask import FlaskIntegration
from werkzeug.middleware.proxy_fix import ProxyFix

from api import api_blueprint
from database import create_db_engine, create_tables
from link_repository import LinkRepository

load_dotenv()


def init_sentry():
    dsn = os.getenv("SENTRY_DSN")
    if not dsn:
        return

    sentry_sdk.init(
        dsn=dsn,
        integrations=[FlaskIntegration()],
        send_default_pii=False,
        traces_sample_rate=None,
    )


def configure_cors(application):
    cors_origins = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
        if origin.strip()
    ]
    CORS(
        application,
        resources={
            r"^/api/.*$": {
                "origins": cors_origins,
                "methods": ["GET", "HEAD", "POST", "PUT", "DELETE", "OPTIONS"],
                "allow_headers": ["Content-Type", "Range"],
                "expose_headers": ["Content-Range"],
            }
        },
    )


def create_app(database_url=None, base_url=None):
    application = Flask(__name__)
    application.wsgi_app = ProxyFix(
        application.wsgi_app,
        x_for=1,
        x_proto=1,
        x_host=1,
    )
    engine = create_db_engine(database_url)
    create_tables(engine)
    application.extensions["db_engine"] = engine
    application.extensions["link_repository"] = LinkRepository(engine)
    application.config["BASE_URL"] = base_url or os.getenv("BASE_URL")
    configure_cors(application)
    application.register_blueprint(api_blueprint)

    return application


init_sentry()
app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")))
