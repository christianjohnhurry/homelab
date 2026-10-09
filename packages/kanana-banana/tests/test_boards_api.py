import pytest


def test_create_and_get(client, api):
    board = api.board("Homelab", repo_url="https://github.com/o/homelab", description="d")
    assert board["name"] == "Homelab"
    assert board["repo_url"] == "https://github.com/o/homelab"

    r = client.get(f"/api/v1/boards/{board['id']}")
    assert r.status_code == 200
    assert r.json() == board


def test_get_missing(client):
    assert client.get("/api/v1/boards/999").status_code == 404


def test_list_ordered_by_name(client, api):
    api.board("Zebra")
    api.board("Apple")
    names = [b["name"] for b in client.get("/api/v1/boards").json()]
    assert names == ["Apple", "Zebra"]


def test_update_partial(client, api):
    board = api.board("Old", description="keep me")
    r = client.patch(f"/api/v1/boards/{board['id']}", json={"name": "New"})
    assert r.status_code == 200
    assert r.json()["name"] == "New"
    assert r.json()["description"] == "keep me"


def test_update_missing(client):
    assert client.patch("/api/v1/boards/999", json={"name": "x"}).status_code == 404


def test_delete_empty(client, api):
    board = api.board()
    assert client.delete(f"/api/v1/boards/{board['id']}").status_code == 204
    assert client.get(f"/api/v1/boards/{board['id']}").status_code == 404


def test_delete_with_tickets_refused(client, api):
    board = api.board()
    api.project(board=board)
    r = client.delete(f"/api/v1/boards/{board['id']}")
    assert r.status_code == 400
    assert "Cannot delete board" in r.json()["detail"]


def test_delete_missing(client):
    assert client.delete("/api/v1/boards/999").status_code == 404


class TestKeys:
    def test_stored_uppercase(self, api):
        assert api.board("Homelab", key="hml")["key"] == "HML"

    @pytest.mark.parametrize("key", ["A", "hml", "ReallyLongBoardKeyIsFine"])
    def test_any_length_of_letters(self, client, key):
        r = client.post("/api/v1/boards", json={"key": key, "name": "x"})
        assert r.status_code == 201
        assert r.json()["key"] == key.upper()

    def test_surrounding_whitespace_trimmed(self, client):
        r = client.post("/api/v1/boards", json={"key": "  hml ", "name": "x"})
        assert r.json()["key"] == "HML"

    @pytest.mark.parametrize("key", ["", "HML1", "HM-L", "HM L", "hml_x", "Ünï"])
    def test_letters_only(self, client, key):
        r = client.post("/api/v1/boards", json={"key": key, "name": "x"})
        assert r.status_code == 422

    def test_required(self, client):
        assert client.post("/api/v1/boards", json={"name": "x"}).status_code == 422

    def test_unique_case_insensitive(self, client, api):
        api.board("Homelab", key="HML")
        r = client.post("/api/v1/boards", json={"key": "hml", "name": "Other"})
        assert r.status_code == 409
        assert "already used" in r.json()["detail"]

    def test_cannot_change(self, client, api):
        board = api.board("Homelab", key="HML")
        r = client.patch(f"/api/v1/boards/{board['id']}", json={"key": "NEW"})
        assert r.status_code == 422
        assert client.get(f"/api/v1/boards/{board['id']}").json()["key"] == "HML"

    def test_filter_by_key(self, client, api):
        api.board("Homelab", key="HML")
        other = api.board("Other", key="OTH")
        assert client.get("/api/v1/boards", params={"key": "oth"}).json() == [other]
        assert client.get("/api/v1/boards", params={"key": "NOPE"}).json() == []
