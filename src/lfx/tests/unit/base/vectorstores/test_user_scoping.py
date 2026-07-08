"""Unit tests for the shared per-user vector-store scoping helpers."""

from types import SimpleNamespace

from lfx.base.vectorstores.user_scoping import runtime_user_id, scoped_collection_name


class TestScopedCollectionName:
    def test_scopes_name_for_a_user(self) -> None:
        scoped = scoped_collection_name("shared", "owner-user")
        assert scoped != "shared"
        assert scoped.startswith("lf_")
        # "lf_" + 16 hex characters
        assert len(scoped) == 19

    def test_is_stable_for_same_inputs(self) -> None:
        assert scoped_collection_name("shared", "owner-user") == scoped_collection_name("shared", "owner-user")

    def test_different_users_get_different_names(self) -> None:
        owner = scoped_collection_name("shared", "owner-user")
        attacker = scoped_collection_name("shared", "attacker-user")
        assert owner != attacker

    def test_different_collections_get_different_names(self) -> None:
        first = scoped_collection_name("collection-a", "owner-user")
        second = scoped_collection_name("collection-b", "owner-user")
        assert first != second

    def test_separator_boundary_is_unambiguous(self) -> None:
        # A bare "{user_id}:{collection_name}" join collides for these two pairs
        # ("a:b" + ":" + "c"  ==  "a" + ":" + "b:c"); length-prefixing must keep
        # them distinct so different users/collections never share a local store.
        assert scoped_collection_name("c", "a:b") != scoped_collection_name("b:c", "a")

    def test_falls_back_when_user_id_is_none(self) -> None:
        assert scoped_collection_name("shared", None) == "shared"

    def test_falls_back_when_user_id_is_literal_none_string(self) -> None:
        # PlaceholderGraph stringifies a missing user id to "None"
        assert scoped_collection_name("shared", "None") == "shared"

    def test_falls_back_when_user_id_is_blank(self) -> None:
        assert scoped_collection_name("shared", "   ") == "shared"

    def test_falls_back_when_collection_name_is_empty(self) -> None:
        assert scoped_collection_name("", "owner-user") == ""

    def test_accepts_non_string_user_id(self) -> None:
        scoped = scoped_collection_name("shared", 1234)
        assert scoped.startswith("lf_")
        assert scoped == scoped_collection_name("shared", "1234")


class TestRuntimeUserId:
    def test_returns_none_without_user_or_graph(self) -> None:
        component = SimpleNamespace()
        assert runtime_user_id(component) is None

    def test_prefers_direct_user_id(self) -> None:
        component = SimpleNamespace(_user_id="u42")
        assert runtime_user_id(component) == "u42"

    def test_falls_back_to_graph_user_id(self) -> None:
        graph = SimpleNamespace(user_id="graph-user")
        vertex = SimpleNamespace(graph=graph)
        component = SimpleNamespace(_user_id=None, _vertex=vertex)
        assert runtime_user_id(component) == "graph-user"

    def test_direct_user_id_wins_over_graph(self) -> None:
        graph = SimpleNamespace(user_id="graph-user")
        vertex = SimpleNamespace(graph=graph)
        component = SimpleNamespace(_user_id="u42", _vertex=vertex)
        assert runtime_user_id(component) == "u42"

    def test_handles_vertex_without_graph(self) -> None:
        component = SimpleNamespace(_user_id=None, _vertex=SimpleNamespace(graph=None))
        assert runtime_user_id(component) is None
