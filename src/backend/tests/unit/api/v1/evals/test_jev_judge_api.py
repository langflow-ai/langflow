from .conftest import create_dataset, create_evaluation, create_flow

JEV_JUDGE = {
    "type": "llm_judge",
    "name": "jev",
    "config": {"model": [{"name": "jev-latest", "provider": "TypeSafe"}], "safety_checks": ["jailbreak"]},
}


class TestJevJudgeRun:
    async def test_should_refuse_to_start_without_a_typesafe_key(self, client, logged_in_headers, monkeypatch):
        monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
        monkeypatch.delenv("LANGFLOW_TYPESAFE_API_KEY", raising=False)
        flow = await create_flow(client, logged_in_headers)
        dataset = await create_dataset(client, logged_in_headers, "jev-no-key", [("a", "a")])
        evaluation = await create_evaluation(client, logged_in_headers, flow["id"], dataset["id"], scorers=[JEV_JUDGE])

        response = await client.post(f"api/v1/evaluations/{evaluation['id']}/runs", json={}, headers=logged_in_headers)

        assert response.status_code == 422
        assert "TypeSafe API key" in response.text
        runs = await client.get(f"api/v1/evaluations/{evaluation['id']}/runs", headers=logged_in_headers)
        assert runs.json()["total"] == 0
