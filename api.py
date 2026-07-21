import json

from flask import Blueprint, current_app, jsonify, redirect, request
from pydantic import ValidationError

from link_repository import DuplicateShortNameError, LinkRepository
from models import Link, LinkPayload

api_blueprint = Blueprint("api", __name__)


def get_link_repository() -> LinkRepository:
    return current_app.extensions["link_repository"]


def error_response(detail, status):
    return jsonify(detail=detail), status


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


def parse_payload():
    try:
        payload = LinkPayload.model_validate(request.get_json(silent=True))
    except ValidationError as error:
        return None, {"errors": error.errors(include_url=False)}
    return payload, None


def serialize_link(link: Link):
    root = current_app.config["BASE_URL"] or request.host_url
    return {
        "id": link.id,
        "original_url": link.original_url,
        "short_name": link.short_name,
        "short_url": f"{root.rstrip('/')}/r/{link.short_name}",
    }


@api_blueprint.get("/ping")
def ping():
    return "pong"


@api_blueprint.get("/api/links")
def list_links():
    try:
        bounds = parse_range(request.args.get("range"))
    except ValueError:
        return error_response("Invalid range", 422)

    links, total, start = get_link_repository().list_links(bounds)
    response = jsonify([serialize_link(link) for link in links])
    if links:
        response.headers["Content-Range"] = (
            f"links {start}-{start + len(links) - 1}/{total}"
        )
    else:
        response.headers["Content-Range"] = f"links */{total}"
    return response


@api_blueprint.post("/api/links")
def create_link():
    payload, validation_detail = parse_payload()
    if validation_detail is not None:
        return error_response(validation_detail, 422)

    try:
        link = get_link_repository().create_link(payload)
    except DuplicateShortNameError:
        return error_response("short_name already exists", 409)
    return jsonify(serialize_link(link)), 201


@api_blueprint.get("/api/links/<int:link_id>")
def get_link(link_id):
    link = get_link_repository().get_link(link_id)
    if link is None:
        return error_response("Not found", 404)
    return jsonify(serialize_link(link))


@api_blueprint.put("/api/links/<int:link_id>")
def update_link(link_id):
    payload, validation_detail = parse_payload()
    if validation_detail is not None:
        return error_response(validation_detail, 422)

    try:
        link = get_link_repository().update_link(link_id, payload)
    except DuplicateShortNameError:
        return error_response("short_name already exists", 409)
    if link is None:
        return error_response("Not found", 404)
    return jsonify(serialize_link(link))


@api_blueprint.delete("/api/links/<int:link_id>")
def delete_link(link_id):
    if not get_link_repository().delete_link(link_id):
        return error_response("Not found", 404)
    return "", 204


@api_blueprint.get("/r/<string:short_name>")
def follow_link(short_name):
    link = get_link_repository().find_by_short_name(short_name)
    if link is None:
        return error_response("Not found", 404)
    return redirect(link.original_url, code=302)


@api_blueprint.app_errorhandler(404)
def handle_not_found(_error):
    return error_response("Not found", 404)
