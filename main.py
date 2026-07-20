import json
import os

import sentry_sdk
from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, request
from flask_cors import CORS
from pydantic import ValidationError
from sentry_sdk.integrations.flask import FlaskIntegration
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select
from werkzeug.middleware.proxy_fix import ProxyFix

from database import create_db_engine, create_tables
from models import Link, LinkPayload

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


def parse_range(value):
    if value is None:
        return None

    try:
        bounds = json.loads(value)
    except (TypeError, ValueError) as error:
        raise ValueError("Invalid range") from error

    if (
        not isinstance(bounds, list)
        or len(bounds) != 2
        or any(type(bound) is not int for bound in bounds)
    ):
        raise ValueError("Invalid range")

    start, end = bounds
    if start < 0 or end < start:
        raise ValueError("Invalid range")
    return start, end


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
    application.config["BASE_URL"] = base_url or os.getenv("BASE_URL")
    cors_origins = [
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS", "http://localhost:5173"
        ).split(",")
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

    def error_response(detail, status):
        return jsonify(detail=detail), status

    def parse_payload():
        try:
            payload = LinkPayload.model_validate(request.get_json(silent=True))
        except ValidationError as error:
            return None, {"errors": error.errors(include_url=False)}
        return payload, None

    def serialize_link(link):
        root = application.config["BASE_URL"] or request.host_url
        return {
            "id": link.id,
            "original_url": link.original_url,
            "short_name": link.short_name,
            "short_url": f"{root.rstrip('/')}/r/{link.short_name}",
        }

    @application.get("/ping")
    def ping():
        return "pong"

    @application.get("/api/links")
    def list_links():
        try:
            bounds = parse_range(request.args.get("range"))
        except ValueError:
            return error_response("Invalid range", 422)

        with Session(engine) as session:
            total = session.exec(select(func.count()).select_from(Link)).one()
            statement = select(Link).order_by(Link.id)
            start = 0
            if bounds is not None:
                start, end = bounds
                statement = statement.offset(start).limit(end - start + 1)
            links = session.exec(statement).all()

        response = jsonify([serialize_link(link) for link in links])
        if links:
            response.headers["Content-Range"] = (
                f"links {start}-{start + len(links) - 1}/{total}"
            )
        else:
            response.headers["Content-Range"] = f"links */{total}"
        return response

    @application.post("/api/links")
    def create_link():
        payload, validation_detail = parse_payload()
        if validation_detail is not None:
            return error_response(validation_detail, 422)

        link = Link.model_validate(payload)
        with Session(engine) as session:
            session.add(link)
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                return error_response("short_name already exists", 409)
            session.refresh(link)
            return jsonify(serialize_link(link)), 201

    @application.get("/api/links/<int:link_id>")
    def get_link(link_id):
        with Session(engine) as session:
            link = session.get(Link, link_id)
            if link is None:
                return error_response("Not found", 404)
            return jsonify(serialize_link(link))

    @application.put("/api/links/<int:link_id>")
    def update_link(link_id):
        payload, validation_detail = parse_payload()
        if validation_detail is not None:
            return error_response(validation_detail, 422)

        with Session(engine) as session:
            link = session.get(Link, link_id)
            if link is None:
                return error_response("Not found", 404)
            link.sqlmodel_update(payload.model_dump())
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                return error_response("short_name already exists", 409)
            session.refresh(link)
            return jsonify(serialize_link(link))

    @application.delete("/api/links/<int:link_id>")
    def delete_link(link_id):
        with Session(engine) as session:
            link = session.get(Link, link_id)
            if link is None:
                return error_response("Not found", 404)
            session.delete(link)
            session.commit()
            return "", 204

    @application.get("/r/<string:short_name>")
    def follow_link(short_name):
        with Session(engine) as session:
            link = session.exec(
                select(Link).where(Link.short_name == short_name)
            ).first()
            if link is None:
                return error_response("Not found", 404)
            return redirect(link.original_url, code=302)

    @application.errorhandler(404)
    def handle_not_found(_error):
        return error_response("Not found", 404)

    return application


init_sentry()
app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")))
