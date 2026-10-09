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
