"""Regression tests for FaissVectorStoreComponent security defaults."""

import pytest

pytest.importorskip("lfx_bundles")
pytest.importorskip("langchain_community")

from lfx.io import BoolInput
from lfx_bundles.faiss.faiss import FaissVectorStoreComponent


class TestFaissVectorStoreComponentDefaults:
    """Regression tests ensuring FAISS component security defaults do not regress."""

    def test_allow_dangerous_deserialization_defaults_to_false(self):
        """Regression test: allow_dangerous_deserialization must default to False.

        This guards against accidentally re-enabling unsafe pickle deserialization
        (RCE vulnerability PVR0699083). Do not change this default to True.
        """
        input_def = next(
            inp
            for inp in FaissVectorStoreComponent.inputs
            if isinstance(inp, BoolInput) and inp.name == "allow_dangerous_deserialization"
        )
        assert input_def.value is False, (
            "allow_dangerous_deserialization must default to False to prevent RCE via malicious pickle files. "
            "See security issue PVR0699083."
        )

    def test_allow_dangerous_deserialization_is_advanced(self):
        """allow_dangerous_deserialization should be an advanced field to reduce accidental enabling."""
        input_def = next(
            inp
            for inp in FaissVectorStoreComponent.inputs
            if isinstance(inp, BoolInput) and inp.name == "allow_dangerous_deserialization"
        )
        assert input_def.advanced is True
