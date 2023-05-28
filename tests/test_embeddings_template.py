from langflow.template.field.base import TemplateField
from langflow.template.frontend_node.embeddings import EmbeddingFrontendNode


def test_format_jina_fields():
    field = TemplateField(name="jina")
    EmbeddingFrontendNode.format_jina_fields(field)
    assert field.show is True
    assert field.advanced is False

    field = TemplateField(name="auth")
    EmbeddingFrontendNode.format_jina_fields(field)
    assert field.password is True
    assert field.show is True
    assert field.advanced is False

    field = TemplateField(name="jina_api_url")
    EmbeddingFrontendNode.format_jina_fields(field)
    assert field.show is True
    assert field.advanced is True
    assert field.display_name == "Jina API URL"
    assert field.password is False


def test_format_openai_fields():
    field = TemplateField(name="openai")
    EmbeddingFrontendNode.format_openai_fields(field)
    assert field.show is True
    assert field.advanced is True
    assert field.display_name == "OpenAI"

    field = TemplateField(name="openai_api_key")
    EmbeddingFrontendNode.format_openai_fields(field)
    assert field.password is True
    assert field.show is True
    assert field.advanced is False


def test_format_field():
    field = TemplateField(name="headers")
    EmbeddingFrontendNode.format_field(field)
    assert field.show is False

    field = TemplateField(name="jina")
    EmbeddingFrontendNode.format_field(field)
    assert field.advanced is False
    assert field.show is True

    field = TemplateField(name="openai")
    EmbeddingFrontendNode.format_field(field)
    assert field.advanced is True
    assert field.show is True
    assert field.display_name == "OpenAI"

    field = TemplateField(name="test_field", required=True)
    EmbeddingFrontendNode.format_field(field)
    assert field.advanced is False
    assert field.show is True
    assert field.required is True
