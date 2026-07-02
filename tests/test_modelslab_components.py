"""Tests for ModelsLab Langflow components.

Run with: pytest tests/test_modelslab_components.py -v
"""

from unittest.mock import MagicMock, patch

import pytest

# ── Helpers ───────────────────────────────────────────────────────────────────


def make_llm_component(**kwargs):
    """Create a ModelsLabModelComponent with mocked Langflow internals."""
    from langflow.components.models.modelslab import ModelsLabModelComponent

    comp = ModelsLabModelComponent.__new__(ModelsLabModelComponent)
    # Set defaults
    comp.api_key = kwargs.get("api_key", "test-key-12345")
    comp.model_name = kwargs.get("model_name", "llama-3.1-8b-uncensored")
    comp.temperature = kwargs.get("temperature", 0.7)
    comp.max_tokens = kwargs.get("max_tokens", 0)
    comp.top_p = kwargs.get("top_p", 1.0)
    comp.n = kwargs.get("n", 1)
    comp.stream = kwargs.get("stream", False)
    comp.base_url = kwargs.get("base_url", "https://modelslab.com/uncensored-chat/v1")
    return comp


def make_image_component(**kwargs):
    from langflow.components.utilities.modelslab_image import ModelsLabImageComponent

    comp = ModelsLabImageComponent.__new__(ModelsLabImageComponent)
    comp.api_key = kwargs.get("api_key", "test-key-12345")
    comp.prompt = kwargs.get("prompt", "a sunset over mountains")
    comp.negative_prompt = kwargs.get("negative_prompt", "")
    comp.model_id = kwargs.get("model_id", "flux")
    comp.width = kwargs.get("width", 1024)
    comp.height = kwargs.get("height", 1024)
    comp.num_inference_steps = kwargs.get("num_inference_steps", 20)
    comp.guidance_scale = kwargs.get("guidance_scale", 7.5)
    comp.seed = kwargs.get("seed", -1)
    comp.samples = kwargs.get("samples", 1)
    comp.poll_timeout = kwargs.get("poll_timeout", 30)
    comp.status = ""
    return comp


# ── LLM Component Tests ───────────────────────────────────────────────────────


class TestModelsLabModelComponent:
    """Tests for the chat LLM component."""

    @patch("langflow.components.models.modelslab.ChatOpenAI")
    def test_build_model_returns_chat_openai(self, MockChatOpenAI):
        mock_llm = MagicMock()
        MockChatOpenAI.return_value = mock_llm

        comp = make_llm_component()
        result = comp.build_model()

        assert result is mock_llm
        MockChatOpenAI.assert_called_once()

    @patch("langflow.components.models.modelslab.ChatOpenAI")
    def test_build_model_passes_correct_base_url(self, MockChatOpenAI):
        MockChatOpenAI.return_value = MagicMock()
        comp = make_llm_component()
        comp.build_model()

        call_kwargs = MockChatOpenAI.call_args.kwargs
        assert call_kwargs["openai_api_base"] == "https://modelslab.com/uncensored-chat/v1"

    @patch("langflow.components.models.modelslab.ChatOpenAI")
    def test_build_model_passes_api_key(self, MockChatOpenAI):
        MockChatOpenAI.return_value = MagicMock()
        comp = make_llm_component(api_key="my-secret-key")
        comp.build_model()

        call_kwargs = MockChatOpenAI.call_args.kwargs
        assert call_kwargs["openai_api_key"] == "my-secret-key"

    @patch("langflow.components.models.modelslab.ChatOpenAI")
    def test_build_model_passes_model_name(self, MockChatOpenAI):
        MockChatOpenAI.return_value = MagicMock()
        comp = make_llm_component(model_name="llama-3.1-70b-uncensored")
        comp.build_model()

        call_kwargs = MockChatOpenAI.call_args.kwargs
        assert call_kwargs["model"] == "llama-3.1-70b-uncensored"

    @patch("langflow.components.models.modelslab.ChatOpenAI")
    def test_build_model_excludes_max_tokens_when_zero(self, MockChatOpenAI):
        MockChatOpenAI.return_value = MagicMock()
        comp = make_llm_component(max_tokens=0)
        comp.build_model()

        call_kwargs = MockChatOpenAI.call_args.kwargs
        assert "max_tokens" not in call_kwargs

    @patch("langflow.components.models.modelslab.ChatOpenAI")
    def test_build_model_includes_max_tokens_when_set(self, MockChatOpenAI):
        MockChatOpenAI.return_value = MagicMock()
        comp = make_llm_component(max_tokens=2048)
        comp.build_model()

        call_kwargs = MockChatOpenAI.call_args.kwargs
        assert call_kwargs["max_tokens"] == 2048

    def test_build_model_raises_without_api_key(self):
        comp = make_llm_component(api_key="")
        with pytest.raises(ValueError, match="API key"):
            comp.build_model()

    def test_display_name(self):
        from langflow.components.models.modelslab import ModelsLabModelComponent

        assert ModelsLabModelComponent.display_name == "ModelsLab"

    def test_has_both_outputs(self):
        from langflow.components.models.modelslab import ModelsLabModelComponent

        output_names = [o.name for o in ModelsLabModelComponent.outputs]
        assert "text_output" in output_names
        assert "model_output" in output_names


# ── Image Component Tests ─────────────────────────────────────────────────────


class TestModelsLabImageComponent:
    """Tests for the image generation component."""

    @patch("langflow.components.utilities.modelslab_image.requests.post")
    def test_generate_image_sync_success(self, mock_post):
        mock_post.return_value = MagicMock(
            ok=True,
            json=lambda: {
                "status": "success",
                "output": ["https://cdn.modelslab.com/test-image.png"],
            },
        )
        mock_post.return_value.raise_for_status = MagicMock()

        comp = make_image_component()
        result = comp.generate_image()

        assert result.data["image_urls"] == ["https://cdn.modelslab.com/test-image.png"]
        assert result.text == "https://cdn.modelslab.com/test-image.png"

    @patch("langflow.components.utilities.modelslab_image.time.sleep")
    @patch("langflow.components.utilities.modelslab_image.requests.post")
    def test_generate_image_async_polling(self, mock_post, mock_sleep):
        mock_post.side_effect = [
            # Initial request — processing
            MagicMock(
                ok=True,
                json=lambda: {"status": "processing", "id": "task-xyz"},
                raise_for_status=MagicMock(),
            ),
            # Poll #1 — done
            MagicMock(
                ok=True,
                json=lambda: {
                    "status": "success",
                    "output": ["https://cdn.modelslab.com/polled.png"],
                },
                raise_for_status=MagicMock(),
            ),
        ]

        comp = make_image_component(poll_timeout=60)
        result = comp.generate_image()

        assert result.data["image_urls"] == ["https://cdn.modelslab.com/polled.png"]
        assert mock_sleep.called

    @patch("langflow.components.utilities.modelslab_image.requests.post")
    def test_generate_image_raises_on_failed_status(self, mock_post):
        mock_post.return_value = MagicMock(
            ok=True,
            json=lambda: {"status": "failed", "message": "Invalid model_id"},
            raise_for_status=MagicMock(),
        )

        comp = make_image_component()
        with pytest.raises(RuntimeError, match="Invalid model_id"):
            comp.generate_image()

    @patch("langflow.components.utilities.modelslab_image.requests.post")
    def test_generate_image_raises_on_http_error(self, mock_post):
        import requests as req

        mock_post.return_value = MagicMock(
            ok=False,
            raise_for_status=MagicMock(side_effect=req.HTTPError("500 Server Error")),
        )

        comp = make_image_component()
        with pytest.raises(RuntimeError, match="API request failed"):
            comp.generate_image()

    def test_generate_image_raises_without_api_key(self):
        comp = make_image_component(api_key="")
        with pytest.raises(ValueError, match="API key"):
            comp.generate_image()

    def test_generate_image_raises_without_prompt(self):
        comp = make_image_component(prompt="")
        with pytest.raises(ValueError, match="Prompt"):
            comp.generate_image()

    @patch("langflow.components.utilities.modelslab_image.requests.post")
    def test_correct_payload_sent(self, mock_post):
        mock_post.return_value = MagicMock(
            ok=True,
            json=lambda: {
                "status": "success",
                "output": ["https://cdn.modelslab.com/img.png"],
            },
            raise_for_status=MagicMock(),
        )

        comp = make_image_component(
            model_id="stable-diffusion-xl-base-1.0",
            prompt="a red dragon",
            width=768,
            height=768,
            num_inference_steps=30,
            guidance_scale=8.0,
            seed=42,
        )
        comp.generate_image()

        _, kwargs = mock_post.call_args
        payload = kwargs["json"]
        assert payload["model_id"] == "stable-diffusion-xl-base-1.0"
        assert payload["prompt"] == "a red dragon"
        assert payload["width"] == "768"
        assert payload["height"] == "768"
        assert payload["num_inference_steps"] == 30
        assert payload["guidance_scale"] == 8.0
        assert payload["seed"] == 42

    @patch("langflow.components.utilities.modelslab_image.requests.post")
    def test_seed_minus_one_excluded_from_payload(self, mock_post):
        mock_post.return_value = MagicMock(
            ok=True,
            json=lambda: {"status": "success", "output": ["https://x.com/img.png"]},
            raise_for_status=MagicMock(),
        )

        comp = make_image_component(seed=-1)
        comp.generate_image()

        _, kwargs = mock_post.call_args
        assert "seed" not in kwargs["json"]

    def test_display_name(self):
        from langflow.components.utilities.modelslab_image import ModelsLabImageComponent

        assert ModelsLabImageComponent.display_name == "ModelsLab Image Generation"
