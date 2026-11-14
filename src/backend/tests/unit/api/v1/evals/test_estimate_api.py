from .conftest import create_dataset, create_flow

JUDGE = [{"name": "judge", "provider": "OpenAI", "metadata": {"cost_per_million_in": 1.0, "cost_per_million_out": 2.0}}]


async def test_should_estimate_a_free_run_for_a_flow_without_models(client, logged_in_headers):
    flow = await create_flow(client, logged_in_headers)
    dataset = await create_dataset(client, logged_in_headers, "est-free", [("hello", "hello"), ("world", None)])
    response = await client.post(
        "api/v1/evaluations/estimate",
        json={"flow_id": flow["id"], "dataset_id": dataset["id"], "scorers": [{"type": "exact_match", "name": "e"}]},
        headers=logged_in_headers,
    )
    assert response.status_code == 200, response.text
    estimate = response.json()
    assert (estimate["items"], estimate["llm_calls"], estimate["tokens_high"]) == (2, 0, 0)
    assert estimate["basis"] == "model"


async def test_should_price_the_judge_before_any_run(client, logged_in_headers):
    flow = await create_flow(client, logged_in_headers)
    dataset = await create_dataset(client, logged_in_headers, "est-judge", [("q1", "a1"), ("q2", "a2"), ("q3", None)])
    response = await client.post(
        "api/v1/evaluations/estimate",
        json={
            "flow_id": flow["id"],
            "dataset_id": dataset["id"],
            "scorers": [{"type": "llm_judge", "name": "judge", "config": {"model": JUDGE}}],
        },
        headers=logged_in_headers,
    )
    estimate = response.json()
    assert estimate["judge_calls"] == 3
    assert estimate["llm_calls"] == 3
    assert 0 < estimate["judge_tokens_low"] < estimate["judge_tokens_high"]
    assert 0 < estimate["cost_low"] < estimate["cost_high"]
    assert estimate["unpriced_models"] == []


async def test_should_hide_a_dataset_of_another_user(client, logged_in_headers, user_two):
    from langflow.services.database.models.evaluation import Dataset
    from langflow.services.deps import session_scope

    flow = await create_flow(client, logged_in_headers)
    async with session_scope() as session:
        foreign = Dataset(user_id=user_two.id, name="theirs-est")
        session.add(foreign)
        await session.flush()
        foreign_id = str(foreign.id)
    response = await client.post(
        "api/v1/evaluations/estimate",
        json={"flow_id": flow["id"], "dataset_id": foreign_id, "scorers": []},
        headers=logged_in_headers,
    )
    assert response.status_code == 404
