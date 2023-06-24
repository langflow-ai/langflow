from langflow.components.field.base import TemplateField
from langflow.components.component.embeddings import EmbeddingComponent


def test_format_jina_fields():
    field = TemplateField(name="jina")
    EmbeddingComponent.format_jina_fields(field)
    assert field.show is True
    assert field.advanced is False

    field = TemplateField(name="auth")
    EmbeddingComponent.format_jina_fields(field)
    assert field.password is True
    assert field.show is True
    assert field.advanced is False

    field = TemplateField(name="jina_api_url")
    EmbeddingComponent.format_jina_fields(field)
    assert field.show is True
    assert field.advanced is True
    assert field.display_name == "Jina API URL"
    assert field.password is False


def test_format_openai_fields():
    field = TemplateField(name="openai")
    EmbeddingComponent.format_openai_fields(field)
    assert field.show is True
    assert field.advanced is True
    assert field.display_name == "OpenAI"

    field = TemplateField(name="openai_api_key")
    EmbeddingComponent.format_openai_fields(field)
    assert field.password is True
    assert field.show is True
    assert field.advanced is False


def test_format_field():
    field = TemplateField(name="headers")
    EmbeddingComponent.format_field(field)
    assert field.show is False

    field = TemplateField(name="jina")
    EmbeddingComponent.format_field(field)
    assert field.advanced is False
    assert field.show is True

    field = TemplateField(name="openai")
    EmbeddingComponent.format_field(field)
    assert field.advanced is True
    assert field.show is True
    assert field.display_name == "OpenAI"

    field = TemplateField(name="test_field", required=True)
    EmbeddingComponent.format_field(field)
    assert field.advanced is False
    assert field.show is True
    assert field.required is True
