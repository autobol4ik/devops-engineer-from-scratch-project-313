import pytest
from sqlmodel import Session, select

from main import create_app
from models import Link


@pytest.fixture
def app():
    return create_app(database_url="sqlite://", base_url="https://short.io/")


@pytest.fixture
def client(app):
    return app.test_client()


def create_link(client, original_url="https://example.com/long", short_name="exmpl"):
    return client.post(
        "/api/links",
        json={"original_url": original_url, "short_name": short_name},
    )


def test_ping(client):
    response = client.get("/ping")

    assert response.status_code == 200
    assert response.get_data(as_text=True) == "pong"


def test_empty_links_list(client):
    response = client.get("/api/links?range=[0,1000]")

    assert response.status_code == 200
    assert response.get_json() == []
    assert response.headers["Content-Range"] == "links */0"


def test_create_and_get_link(client):
    created = create_link(client)

    assert created.status_code == 201
    assert created.get_json() == {
        "id": 1,
        "original_url": "https://example.com/long",
        "short_name": "exmpl",
        "short_url": "https://short.io/r/exmpl",
    }

    fetched = client.get("/api/links/1")
    assert fetched.status_code == 200
    assert fetched.get_json() == created.get_json()


def test_list_links_is_ordered_by_id(client):
    first = create_link(client, short_name="first").get_json()
    second = create_link(client, short_name="second").get_json()

    response = client.get("/api/links")

    assert response.status_code == 200
    assert response.get_json() == [first, second]
    assert response.headers["Content-Range"] == "links 0-1/2"


def test_links_pagination_uses_inclusive_bounds(client):
    for index in range(12):
        create_link(client, short_name=f"link-{index}")

    first_page = client.get("/api/links?range=[0, 9]")
    second_page = client.get("/api/links?range=[5, 9]")

    assert first_page.status_code == 200
    assert len(first_page.get_json()) == 10
    assert first_page.headers["Content-Range"] == "links 0-9/12"
    assert [link["id"] for link in second_page.get_json()] == [6, 7, 8, 9, 10]
    assert second_page.headers["Content-Range"] == "links 5-9/12"


def test_links_pagination_clamps_header_to_returned_rows(client):
    for index in range(3):
        create_link(client, short_name=f"link-{index}")

    response = client.get("/api/links?range=[1, 100]")

    assert [link["id"] for link in response.get_json()] == [2, 3]
    assert response.headers["Content-Range"] == "links 1-2/3"


def test_links_pagination_outside_collection_is_empty(client):
    create_link(client)

    response = client.get("/api/links?range=[10, 20]")

    assert response.status_code == 200
    assert response.get_json() == []
    assert response.headers["Content-Range"] == "links */1"


@pytest.mark.parametrize(
    "value",
    ["invalid", "{}", "[0]", "[0, 1, 2]", "[-1, 2]", "[2, 1]", "[true, 2]"],
)
def test_invalid_pagination_range(client, value):
    response = client.get("/api/links", query_string={"range": value})

    assert response.status_code == 422
    assert response.get_json() == {"detail": "Invalid range"}


def test_update_link(client):
    link_id = create_link(client).get_json()["id"]

    response = client.put(
        f"/api/links/{link_id}",
        json={
            "original_url": "https://example.org/updated",
            "short_name": "updated",
        },
    )

    assert response.status_code == 200
    assert response.get_json() == {
        "id": link_id,
        "original_url": "https://example.org/updated",
        "short_name": "updated",
        "short_url": "https://short.io/r/updated",
    }


def test_delete_link(client):
    link_id = create_link(client).get_json()["id"]

    response = client.delete(f"/api/links/{link_id}")

    assert response.status_code == 204
    assert response.data == b""
    assert client.get(f"/api/links/{link_id}").status_code == 404


@pytest.mark.parametrize("method", ["get", "put", "delete"])
def test_missing_link_returns_json_404(client, method):
    kwargs = {}
    if method == "put":
        kwargs["json"] = {
            "original_url": "https://example.com",
            "short_name": "missing",
        }

    response = getattr(client, method)("/api/links/999", **kwargs)

    assert response.status_code == 404
    assert response.get_json() == {"detail": "Not found"}


@pytest.mark.parametrize(
    "payload",
    [
        None,
        {},
        {"original_url": "https://example.com"},
        {"short_name": "short"},
        {"original_url": "", "short_name": "short"},
        {"original_url": "https://example.com", "short_name": "   "},
        {"original_url": 1, "short_name": "short"},
    ],
)
def test_invalid_create_payload(client, payload):
    response = client.post("/api/links", json=payload)

    assert response.status_code == 422
    detail = response.get_json()["detail"]
    assert isinstance(detail, dict)
    assert detail["errors"]


def test_partial_update_is_invalid(client):
    link_id = create_link(client).get_json()["id"]

    response = client.put(
        f"/api/links/{link_id}",
        json={"short_name": "new-name"},
    )

    assert response.status_code == 422
    detail = response.get_json()["detail"]
    assert isinstance(detail, dict)
    assert detail["errors"]


def test_duplicate_name_has_same_error_for_create_and_update(client):
    first_id = create_link(client, short_name="taken").get_json()["id"]
    second_id = create_link(client, short_name="free").get_json()["id"]

    duplicate_create = create_link(client, short_name="taken")
    duplicate_update = client.put(
        f"/api/links/{second_id}",
        json={"original_url": "https://example.net", "short_name": "taken"},
    )

    expected = {"detail": "short_name already exists"}
    assert duplicate_create.status_code == 409
    assert duplicate_create.get_json() == expected
    assert duplicate_update.status_code == 409
    assert duplicate_update.get_json() == expected
    assert client.get(f"/api/links/{first_id}").status_code == 200


def test_created_at_is_set_by_database_and_not_exposed(app, client):
    response = create_link(client)
    engine = app.extensions["db_engine"]

    with Session(engine) as session:
        link = session.exec(select(Link)).one()

    assert link.created_at is not None
    assert "created_at" not in response.get_json()


def test_cors_allows_local_frontend(client):
    response = client.get(
        "/api/links",
        headers={"Origin": "http://localhost:5173"},
    )

    assert response.headers["Access-Control-Allow-Origin"] == (
        "http://localhost:5173"
    )
    assert response.headers["Access-Control-Expose-Headers"] == "Content-Range"


def test_cors_preflight_allows_api_headers(client):
    response = client.options(
        "/api/links",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type, Range",
        },
    )

    assert response.status_code == 200
    assert response.headers["Access-Control-Allow-Origin"] == (
        "http://localhost:5173"
    )
    assert "POST" in response.headers["Access-Control-Allow-Methods"]
    assert "Content-Type" in response.headers["Access-Control-Allow-Headers"]
    assert "Range" in response.headers["Access-Control-Allow-Headers"]


def test_cors_rejects_unknown_origin(client):
    response = client.get(
        "/api/links",
        headers={"Origin": "https://example.com"},
    )

    assert "Access-Control-Allow-Origin" not in response.headers


def test_short_link_redirects_to_original_url(client):
    create_link(client, original_url="https://example.com/page", short_name="go")

    response = client.get("/r/go")

    assert response.status_code == 302
    assert response.headers["Location"] == "https://example.com/page"


def test_forwarded_headers_are_used_for_short_url():
    application = create_app(database_url="sqlite://")
    client = application.test_client()

    response = client.post(
        "/api/links",
        json={"original_url": "https://example.com", "short_name": "secure"},
        headers={
            "X-Forwarded-Host": "short.example",
            "X-Forwarded-Proto": "https",
        },
    )

    assert response.status_code == 201
    assert response.get_json()["short_url"] == "https://short.example/r/secure"


def test_missing_short_link_returns_json_404(client):
    response = client.get("/r/missing")

    assert response.status_code == 404
    assert response.get_json() == {"detail": "Not found"}
