from uuid import uuid4

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
