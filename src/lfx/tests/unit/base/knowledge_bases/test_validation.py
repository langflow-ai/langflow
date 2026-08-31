import pytest
from lfx.base.knowledge_bases.validation import is_valid_collection_name, validate_collection_name


@pytest.mark.parametrize(
    "name",
    [
        "abc",
        "docs.v2",
        "kb_cooking",
        "a-b",
        "a" * 512,
        "topology+collection",
    ],
)
def test_collection_name_validation_accepts_chroma_compatible_names(name: str) -> None:
    assert is_valid_collection_name(name)
    validate_collection_name(name)


@pytest.mark.parametrize(
    "name",
    [
        "ab",
        "a" * 513,
        "Q&A_docs",
        "catalogo_",
        "_catalogo",
        "catálogo",
        "日本語",
        "docs..v2",
        "127.0.0.1",
        "2001:db8::1",
        "topology+collection+extra",
    ],
)
def test_collection_name_validation_rejects_names_chroma_cannot_use(name: str) -> None:
    assert not is_valid_collection_name(name)
    with pytest.raises(ValueError, match="3-512 characters"):
        validate_collection_name(name)


def test_local_chroma_name_length_is_limited_by_filesystem_segment() -> None:
    validate_collection_name("a" * 255, local=True)
    with pytest.raises(ValueError, match="at most 255"):
        validate_collection_name("a" * 256, local=True)
