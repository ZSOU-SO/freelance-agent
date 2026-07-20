def test_post_analysis_persists_unified_result(client) -> None:
    response = client.post(
        "/api/v1/analyses",
        json={"requirement_text": "开发一个带后台管理的企业官网"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["analysis_mode"] == "local_fallback"
    assert body["quote"]["pricing"]["currency"] == "CNY"
    assert client.get(f"/api/v1/analyses/{body['id']}").json() == body


def test_list_analyses_returns_newest_first_page(client) -> None:
    first = client.post(
        "/api/v1/analyses", json={"requirement_text": "开发企业官网"}
    ).json()
    second = client.post(
        "/api/v1/analyses", json={"requirement_text": "开发微信小程序"}
    ).json()

    response = client.get("/api/v1/analyses?limit=1&offset=0")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert body["items"][0]["id"] == second["id"]
    assert body["items"][0]["id"] != first["id"]


def test_blank_requirement_returns_422(client) -> None:
    response = client.post(
        "/api/v1/analyses", json={"requirement_text": "   "}
    )
    assert response.status_code == 422


def test_health_reports_local_mode_without_key(client) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "freelance-agent",
        "analysis_mode": "local_fallback",
    }


def test_missing_analysis_returns_404(client) -> None:
    response = client.get("/api/v1/analyses/missing")
    assert response.status_code == 404
