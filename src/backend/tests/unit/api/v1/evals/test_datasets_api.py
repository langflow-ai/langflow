import asyncio
from urllib.parse import quote
from uuid import UUID, uuid4

import pytest
from langflow.services.deps import session_scope

from .conftest import create_dataset


class TestDatasetCrud:
    async def test_should_create_list_rename_and_delete(self, client, logged_in_headers):
        created = await client.post("api/v1/datasets/", json={"name": " support-qa "}, headers=logged_in_headers)
        assert created.status_code == 201
        dataset = created.json()
        assert dataset["name"] == "support-qa"
        assert dataset["item_count"] == 0

        listed = await client.get("api/v1/datasets/", params={"search": "support"}, headers=logged_in_headers)
        assert [d["id"] for d in listed.json()["items"]] == [dataset["id"]]

        renamed = await client.patch(
            f"api/v1/datasets/{dataset['id']}", json={"name": "renamed"}, headers=logged_in_headers
        )
        assert renamed.json()["name"] == "renamed"

        deleted = await client.delete(f"api/v1/datasets/{dataset['id']}", headers=logged_in_headers)
        assert deleted.status_code == 204
        missing = await client.get(f"api/v1/datasets/{dataset['id']}", headers=logged_in_headers)
        assert missing.status_code == 404

    async def test_should_refuse_duplicate_names_for_the_same_user(self, client, logged_in_headers):
        await client.post("api/v1/datasets/", json={"name": "dup"}, headers=logged_in_headers)
        again = await client.post("api/v1/datasets/", json={"name": "dup"}, headers=logged_in_headers)
        assert again.status_code == 409

    async def test_should_reject_blank_names(self, client, logged_in_headers):
        response = await client.post("api/v1/datasets/", json={"name": "   "}, headers=logged_in_headers)
        assert response.status_code == 422

    async def test_should_treat_like_wildcards_in_search_literally(self, client, logged_in_headers):
        await client.post("api/v1/datasets/", json={"name": "100% done"}, headers=logged_in_headers)
        await client.post("api/v1/datasets/", json={"name": "1000 done"}, headers=logged_in_headers)
        listed = await client.get("api/v1/datasets/", params={"search": "100%"}, headers=logged_in_headers)
        assert [d["name"] for d in listed.json()["items"]] == ["100% done"]

    async def test_should_require_authentication(self, client):
        response = await client.get("api/v1/datasets/")
        assert response.status_code in {401, 403}

    async def test_should_hide_other_users_datasets(self, client, logged_in_headers, user_two):
        async with session_scope() as session:
            from langflow.services.database.models.evaluation import Dataset

            foreign = Dataset(user_id=user_two.id, name="theirs")
            session.add(foreign)
            await session.flush()
            foreign_id = foreign.id
        for method, path in (
            ("get", f"api/v1/datasets/{foreign_id}"),
            ("get", f"api/v1/datasets/{foreign_id}/items"),
            ("delete", f"api/v1/datasets/{foreign_id}"),
            ("get", f"api/v1/datasets/{foreign_id}/export"),
        ):
            response = await getattr(client, method)(path, headers=logged_in_headers)
            assert response.status_code == 404, (method, path, response.status_code)
        listed = await client.get("api/v1/datasets/", headers=logged_in_headers)
        assert str(foreign_id) not in {d["id"] for d in listed.json()["items"]}

    async def test_should_return_404_for_unknown_ids(self, client, logged_in_headers):
        response = await client.get(f"api/v1/datasets/{uuid4()}", headers=logged_in_headers)
        assert response.status_code == 404

    async def test_should_let_a_superuser_read_and_duplicate_another_users_dataset(
        self, client, logged_in_headers_super_user, user_two
    ):
        from langflow.services.database.models.evaluation import Dataset, DatasetItem

        async with session_scope() as session:
            theirs = Dataset(user_id=user_two.id, name="evl-ds-priv")
            session.add(theirs)
            await session.flush()
            session.add_all(
                [DatasetItem(dataset_id=theirs.id, position=i, input={"text": t}) for i, t in enumerate("ab")]
            )
            theirs_id = str(theirs.id)

        read = await client.get(f"api/v1/datasets/{theirs_id}", headers=logged_in_headers_super_user)
        items = await client.get(f"api/v1/datasets/{theirs_id}/items", headers=logged_in_headers_super_user)
        copy = await client.post(f"api/v1/datasets/{theirs_id}/duplicate", headers=logged_in_headers_super_user)

        assert read.status_code == 200
        assert items.json()["total"] == 2
        assert copy.status_code == 201, copy.text
        assert (copy.json()["name"], copy.json()["item_count"]) == ("evl-ds-priv (copy)", 2)
        async with session_scope() as session:
            copied = await session.get(Dataset, UUID(copy.json()["id"]))
            assert copied.user_id != user_two.id


class TestDatasetItems:
    async def test_should_add_edit_delete_and_bump_revision(self, client, logged_in_headers):
        dataset = await create_dataset(client, logged_in_headers, "items", [("q1", "a1"), ("q2", None)])
        page = (await client.get(f"api/v1/datasets/{dataset['id']}/items", headers=logged_in_headers)).json()
        assert page["total"] == 2
        first, second = page["items"]
        assert (first["position"], second["position"]) == (0, 1)
        assert second["expected_output"] is None

        edited = await client.patch(
            f"api/v1/datasets/{dataset['id']}/items/{first['id']}",
            json={"clear_expected_output": True, "input": "q1 edited"},
            headers=logged_in_headers,
        )
        assert edited.json()["input"] == "q1 edited"
        assert edited.json()["expected_output"] is None

        removed = await client.post(
            f"api/v1/datasets/{dataset['id']}/items/delete", json={"ids": [second["id"]]}, headers=logged_in_headers
        )
        assert removed.json() == {"deleted": 1}
        after = (await client.get(f"api/v1/datasets/{dataset['id']}", headers=logged_in_headers)).json()
        assert after["item_count"] == 1
        assert after["revision"] > dataset["revision"]

    async def test_should_delete_more_items_than_one_add_request_holds(self, client, logged_in_headers):
        dataset = await create_dataset(client, logged_in_headers, "big", [(f"q{i}", None) for i in range(999)])
        page = await client.get(f"api/v1/datasets/{dataset['id']}/items?size=5000", headers=logged_in_headers)
        ids = [item["id"] for item in page.json()["items"]]

        removed = await client.post(
            f"api/v1/datasets/{dataset['id']}/items/delete", json={"ids": ids}, headers=logged_in_headers
        )

        assert removed.status_code == 200, removed.text
        assert removed.json() == {"deleted": 999}

    async def test_should_refuse_rows_past_the_dataset_limit(self, client, logged_in_headers, monkeypatch):
        from langflow.services.evaluations import dataset_service

        monkeypatch.setattr(dataset_service, "MAX_DATASET_ITEMS", 3)
        dataset = await create_dataset(client, logged_in_headers, "capped", [("a", None), ("b", None)])

        response = await client.post(
            f"api/v1/datasets/{dataset['id']}/items",
            json={"items": [{"input": "c"}, {"input": "d"}]},
            headers=logged_in_headers,
        )

        assert response.status_code == 422
        assert "at most 3 rows" in response.json()["detail"]

    async def test_should_reject_a_delete_larger_than_one_item_page(self, client, logged_in_headers):
        dataset = await create_dataset(client, logged_in_headers, "huge-delete", [])

        response = await client.post(
            f"api/v1/datasets/{dataset['id']}/items/delete",
            json={"ids": [str(uuid4()) for _ in range(5001)]},
            headers=logged_in_headers,
        )

        assert response.status_code == 422

    async def test_should_reject_an_empty_input(self, client, logged_in_headers):
        dataset = await create_dataset(client, logged_in_headers, "strict", [])
        response = await client.post(
            f"api/v1/datasets/{dataset['id']}/items", json={"items": [{"input": ""}]}, headers=logged_in_headers
        )
        assert response.status_code == 422

    async def test_should_duplicate_with_items(self, client, logged_in_headers):
        dataset = await create_dataset(client, logged_in_headers, "orig", [("q", "a")])
        copy = await client.post(f"api/v1/datasets/{dataset['id']}/duplicate", headers=logged_in_headers)
        assert copy.status_code == 201
        assert copy.json()["name"] == "orig (copy)"
        assert copy.json()["item_count"] == 1
        second = await client.post(f"api/v1/datasets/{dataset['id']}/duplicate", headers=logged_in_headers)
        assert second.json()["name"] == "orig (copy) 2"


class TestCsv:
    async def test_should_preview_import_and_export(self, client, logged_in_headers):
        dataset = await create_dataset(client, logged_in_headers, "csv", [])
        content = "﻿question;answer\nWhat is 2+2?;4\n;orphan\n=HYPERLINK(1);x\n".encode()
        files = {"file": ("data.csv", content, "text/csv")}
        preview = await client.post(
            f"api/v1/datasets/{dataset['id']}/import/preview", files=files, headers=logged_in_headers
        )
        assert preview.status_code == 200
        assert preview.json()["headers"] == ["question", "answer"]

        imported = await client.post(
            f"api/v1/datasets/{dataset['id']}/import",
            files={"file": ("data.csv", content, "text/csv")},
            data={"input_column": "question", "expected_column": "answer"},
            headers=logged_in_headers,
        )
        assert imported.status_code == 200, imported.text
        assert imported.json()["imported"] == 2
        assert imported.json()["skipped"] == [{"row": 3, "reason": "Input is empty"}]

        exported = await client.get(f"api/v1/datasets/{dataset['id']}/export", headers=logged_in_headers)
        assert exported.status_code == 200
        assert "attachment" in exported.headers["content-disposition"]
        assert "'=HYPERLINK(1),x" in exported.text

    @pytest.mark.parametrize("name", ["日本語", "中文", "한국어"])
    async def test_should_export_a_dataset_named_in_a_cjk_script(self, client, logged_in_headers, name):
        dataset = await create_dataset(client, logged_in_headers, name, [("q", "a")])

        exported = await client.get(f"api/v1/datasets/{dataset['id']}/export", headers=logged_in_headers)

        assert exported.status_code == 200
        disposition = exported.headers["content-disposition"]
        assert f"filename*=UTF-8''{quote(name + '.csv', safe='')}" in disposition
        assert disposition.isascii()

    async def test_should_reject_a_non_utf8_upload(self, client, logged_in_headers):
        dataset = await create_dataset(client, logged_in_headers, "latin", [])
        files = {"file": ("data.csv", "q\nação\n".encode("latin-1"), "text/csv")}
        response = await client.post(
            f"api/v1/datasets/{dataset['id']}/import/preview", files=files, headers=logged_in_headers
        )
        assert response.status_code == 422
        assert "UTF-8" in response.json()["detail"]

    async def test_should_reject_an_unknown_column(self, client, logged_in_headers):
        dataset = await create_dataset(client, logged_in_headers, "cols", [])
        response = await client.post(
            f"api/v1/datasets/{dataset['id']}/import",
            files={"file": ("d.csv", b"q,a\n1,2\n", "text/csv")},
            data={"input_column": "nope"},
            headers=logged_in_headers,
        )
        assert response.status_code == 422


class TestDatasetExamples:
    async def test_should_list_the_examples_with_their_sizes(self, client, logged_in_headers):
        response = await client.get("api/v1/datasets/examples", headers=logged_in_headers)
        assert response.status_code == 200
        examples = response.json()
        assert [example["key"] for example in examples] == ["support-triage", "grounded-answers", "safety-checks"]
        assert all(example["item_count"] >= 10 for example in examples)

    async def test_should_create_a_dataset_with_the_example_rows(self, client, logged_in_headers):
        created = await client.post("api/v1/datasets/examples/support-triage", headers=logged_in_headers)
        assert created.status_code == 201
        dataset = created.json()
        assert dataset["name"] == "Support ticket triage"
        assert dataset["item_count"] == 12

        items = await client.get(f"api/v1/datasets/{dataset['id']}/items", headers=logged_in_headers)
        first = items.json()["items"][0]
        assert first["input"] == "I was charged twice for my subscription this month."
        assert first["expected_output"] == "billing"

    async def test_should_name_an_example_dataset_in_the_callers_language(self, client, logged_in_headers):
        labels = {"name": "Triagem de chamados", "description": "Classifique cada mensagem."}

        created = await client.post("api/v1/datasets/examples/support-triage", json=labels, headers=logged_in_headers)

        assert created.status_code == 201, created.text
        assert (created.json()["name"], created.json()["description"]) == (labels["name"], labels["description"])
        assert created.json()["item_count"] == 12

    async def test_should_describe_a_filled_dataset_in_the_callers_language(self, client, logged_in_headers):
        dataset_id = (await client.post("api/v1/datasets/", json={"name": "Vazio"}, headers=logged_in_headers)).json()[
            "id"
        ]

        filled = await client.post(
            f"api/v1/datasets/{dataset_id}/examples/grounded-answers",
            json={"description": "Respostas com base no contexto."},
            headers=logged_in_headers,
        )

        assert filled.status_code == 200, filled.text
        assert (filled.json()["name"], filled.json()["description"]) == ("Vazio", "Respostas com base no contexto.")

    async def test_should_pick_a_free_name_when_added_twice(self, client, logged_in_headers):
        await client.post("api/v1/datasets/examples/safety-checks", headers=logged_in_headers)
        again = await client.post("api/v1/datasets/examples/safety-checks", headers=logged_in_headers)
        assert again.status_code == 201
        assert again.json()["name"] == "Safety and prompt injection 2"

    async def test_should_return_404_for_an_unknown_example(self, client, logged_in_headers):
        response = await client.post("api/v1/datasets/examples/nope", headers=logged_in_headers)
        assert response.status_code == 404

    async def test_should_require_authentication(self, client):
        response = await client.post("api/v1/datasets/examples/support-triage")
        assert response.status_code in {401, 403}

    async def test_should_fill_an_existing_dataset_with_the_example_rows(self, client, logged_in_headers):
        created = await client.post("api/v1/datasets/", json={"name": "Mine"}, headers=logged_in_headers)
        dataset_id = created.json()["id"]

        filled = await client.post(f"api/v1/datasets/{dataset_id}/examples/grounded-answers", headers=logged_in_headers)

        assert filled.status_code == 200, filled.text
        body = filled.json()
        assert (body["id"], body["name"], body["item_count"]) == (dataset_id, "Mine", 10)
        assert body["description"]

    async def test_should_keep_an_existing_description_and_append_rows(self, client, logged_in_headers):
        created = await client.post(
            "api/v1/datasets/", json={"name": "Kept", "description": "My own"}, headers=logged_in_headers
        )
        dataset_id = created.json()["id"]
        await client.post(
            f"api/v1/datasets/{dataset_id}/items",
            json={"items": [{"input": "first", "expected_output": None}]},
            headers=logged_in_headers,
        )

        filled = await client.post(f"api/v1/datasets/{dataset_id}/examples/safety-checks", headers=logged_in_headers)

        assert filled.json()["description"] == "My own"
        assert filled.json()["item_count"] == 11
        items = await client.get(f"api/v1/datasets/{dataset_id}/items", headers=logged_in_headers)
        assert items.json()["items"][0]["input"] == "first"

    async def test_should_hide_another_users_dataset_from_example_fill(self, client, logged_in_headers, user_two):
        created = await client.post("api/v1/datasets/", json={"name": "Private"}, headers=logged_in_headers)
        credentials = {"username": user_two.username, "password": "hashed_password"}  # pragma: allowlist secret
        login = await client.post("api/v1/login", data=credentials)
        other_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        response = await client.post(
            f"api/v1/datasets/{created.json()['id']}/examples/support-triage", headers=other_headers
        )

        assert response.status_code == 404

    async def test_should_return_404_when_filling_with_an_unknown_example(self, client, logged_in_headers):
        created = await client.post("api/v1/datasets/", json={"name": "Unknown"}, headers=logged_in_headers)

        response = await client.post(f"api/v1/datasets/{created.json()['id']}/examples/nope", headers=logged_in_headers)

        assert response.status_code == 404


def _sqlite_lock_error():
    import sqlite3

    from sqlalchemy.exc import OperationalError

    return OperationalError("INSERT INTO dataset_item ...", {}, sqlite3.OperationalError("database is locked"))


class TestDatabaseBusy:
    async def test_should_retry_a_write_that_lost_a_snapshot_race(self, client, logged_in_headers, monkeypatch):
        from langflow.services.evaluations import dataset_service

        dataset = await create_dataset(client, logged_in_headers, "busy-once", [])
        real_add = dataset_service.add_items
        calls = {"count": 0}

        async def lose_once(*args, **kwargs):
            calls["count"] += 1
            if calls["count"] == 1:
                raise _sqlite_lock_error()
            return await real_add(*args, **kwargs)

        monkeypatch.setattr(dataset_service, "add_items", lose_once)

        response = await client.post(
            f"api/v1/datasets/{dataset['id']}/items", json={"items": [{"input": "x"}]}, headers=logged_in_headers
        )

        assert response.status_code == 201, response.text
        assert calls["count"] == 2

    async def test_should_answer_503_at_once_when_another_writer_held_the_lock(
        self, client, logged_in_headers, monkeypatch
    ):
        from langflow.api.v1 import evals_errors
        from langflow.services.evaluations import dataset_service

        dataset = await create_dataset(client, logged_in_headers, "busy-long", [])
        calls = {"count": 0}

        async def wait_then_fail(*_args, **_kwargs):
            calls["count"] += 1
            await asyncio.sleep(0.05)
            raise _sqlite_lock_error()

        monkeypatch.setattr(evals_errors, "LOCK_WAIT_GIVE_UP_SECONDS", 0.01)
        monkeypatch.setattr(dataset_service, "add_items", wait_then_fail)

        response = await client.post(
            f"api/v1/datasets/{dataset['id']}/items", json={"items": [{"input": "x"}]}, headers=logged_in_headers
        )

        assert response.status_code == 503
        assert response.headers["retry-after"] == "1"
        assert calls["count"] == 1

    async def test_should_answer_503_when_reading_runs_meets_a_locked_database(
        self, client, logged_in_headers, monkeypatch
    ):
        from langflow.services.evaluations import run_service

        from .conftest import create_evaluation, create_flow

        flow = await create_flow(client, logged_in_headers)
        dataset = await create_dataset(client, logged_in_headers, "busy-runs", [("a", "a")])
        evaluation = await create_evaluation(client, logged_in_headers, flow["id"], dataset["id"])

        async def locked(*_args, **_kwargs):
            raise _sqlite_lock_error()

        monkeypatch.setattr(run_service, "reconcile_runs", locked)

        response = await client.get(f"api/v1/evaluations/{evaluation['id']}/runs", headers=logged_in_headers)

        assert response.status_code == 503
        assert response.headers["retry-after"] == "1"
        assert "INSERT" not in response.text
