"""Tests for langflow.schema.properties module."""

from langflow.schema.properties import Properties, Source, Usage


class TestSource:
    def test_defaults(self):
        s = Source()
        assert s.id is None
        assert s.display_name is None
        assert s.source is None

    def test_with_values(self):
        s = Source(id="src-1", display_name="GPT-4", source="gpt-4o")
        assert s.id == "src-1"
        assert s.display_name == "GPT-4"
        assert s.source == "gpt-4o"


class TestUsage:
    def test_defaults(self):
        u = Usage()
        assert u.input_tokens is None
        assert u.output_tokens is None
        assert u.total_tokens is None

    def test_with_values(self):
        u = Usage(input_tokens=100, output_tokens=50, total_tokens=150)
        assert u.input_tokens == 100
        assert u.output_tokens == 50
        assert u.total_tokens == 150


class TestProperties:
    def test_defaults(self):
        p = Properties()
        assert p.text_color is None
        assert p.background_color is None
        assert p.edited is False
        assert isinstance(p.source, Source)
        assert p.icon is None
        assert p.allow_markdown is False
        assert p.positive_feedback is None
        assert p.state == "complete"
        assert p.targets == []
        assert p.usage is None
        assert p.build_duration is None

    def test_source_string_converted(self):
        p = Properties(source="gpt-4o")
        assert isinstance(p.source, Source)
        assert p.source.id == "gpt-4o"
        assert p.source.display_name == "gpt-4o"
        assert p.source.source == "gpt-4o"

    def test_source_none_becomes_default(self):
        p = Properties(source=None)
        assert isinstance(p.source, Source)
        assert p.source.id is None

    def test_source_dict(self):
        p = Properties(source={"id": "s1", "display_name": "My Source", "source": "src"})
        assert isinstance(p.source, Source)
        assert p.source.id == "s1"

    def test_source_serialization(self):
        p = Properties(source=Source(id="s1", display_name="D", source="src"))
        d = p.model_dump()
        assert isinstance(d["source"], dict)
        assert d["source"]["id"] == "s1"

    def test_with_usage(self):
        p = Properties(usage=Usage(input_tokens=10, output_tokens=20))
        assert p.usage.input_tokens == 10

    def test_state_partial(self):
        p = Properties(state="partial")
        assert p.state == "partial"

    def test_build_duration(self):
        p = Properties(build_duration=1.5)
        assert p.build_duration == 1.5

    def test_targets(self):
        p = Properties(targets=["a", "b"])
        assert p.targets == ["a", "b"]
