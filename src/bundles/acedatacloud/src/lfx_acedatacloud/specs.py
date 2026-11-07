"""Reviewed first-run routes and fields for the 17 submitted service families.

The public Dify plugins and Ace Data Cloud API guides are the protocol sources.
This bundle intentionally exposes one common first-run action per family; the
advanced field accepts only fields on that route, and never changes its path.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Field:
    name: str
    label: str
    kind: str = "text"
    default: Any = ""
    required: bool = False
    options: tuple[str, ...] = ()


@dataclass(frozen=True)
class Service:
    name: str
    display: str
    path: str
    task_path: str | None
    fields: tuple[Field, ...]
    fixed: tuple[tuple[str, Any], ...] = ()
    advanced: tuple[str, ...] = ()
    prompt_as_content: bool = False
    fish_model_header: bool = False


SERVICES: dict[str, Service] = {
    "gpt_image": Service(
        "gpt_image",
        "GPT Image",
        "/openai/images/generations",
        "/openai/tasks",
        (
            Field("prompt", "Prompt", "multiline", required=True),
            Field("model", "Model", default="gpt-image-2", options=("gpt-image-2",)),
            Field("size", "Size", default="1024x1024"),
            Field(
                "quality",
                "Quality",
                default="low",
                options=("low", "medium", "high", "auto"),
            ),
            Field("n", "Image count", "int", 1),
        ),
        advanced=(
            "background",
            "moderation",
            "output_format",
            "response_format",
            "style",
            "callback_url",
            "async",
        ),
    ),
    "suno": Service(
        "suno",
        "Suno",
        "/suno/audios",
        "/suno/tasks",
        (
            Field("prompt", "Prompt", "multiline", required=True),
            Field("model", "Model", default="chirp-v6", options=("chirp-v6",)),
            Field("instrumental", "Instrumental", "bool", default=True),
            Field("duration", "Target duration (seconds)", "int", 10),
        ),
        fixed=(("action", "generate"),),
        advanced=("style", "title", "callback_url", "async"),
    ),
    "seedance": Service(
        "seedance",
        "Seedance",
        "/seedance/videos",
        "/seedance/tasks",
        (
            Field("prompt", "Prompt", "multiline", required=True),
            Field(
                "model",
                "Model",
                default="doubao-seedance-2-0-mini-260615",
                options=("doubao-seedance-2-0-mini-260615",),
            ),
            Field("duration", "Duration (seconds)", "int", 4),
            Field("resolution", "Resolution", default="480p", options=("480p",)),
            Field("ratio", "Aspect ratio", default="16:9"),
            Field("generate_audio", "Generate audio", "bool", default=False),
        ),
        advanced=("seed", "camerafixed", "watermark", "callback_url", "async"),
        prompt_as_content=True,
    ),
    "fish_audio": Service(
        "fish_audio",
        "Fish Audio",
        "/fish/tts",
        "/fish/tasks",
        (
            Field("text", "Text", "multiline", required=True),
            Field("model", "Model", default="s2-pro", options=("s2-pro",)),
            Field("format", "Format", default="mp3", options=("mp3", "wav")),
            Field("reference_id", "Voice reference ID"),
        ),
        advanced=(
            "sample_rate",
            "mp3_bitrate",
            "temperature",
            "top_p",
            "callback_url",
            "async",
        ),
        fish_model_header=True,
    ),
    "seedream": Service(
        "seedream",
        "Seedream",
        "/seedream/images",
        "/seedream/tasks",
        (
            Field("prompt", "Prompt", "multiline", required=True),
            Field(
                "model",
                "Model",
                default="doubao-seedream-5-0-lite-260128",
                options=("doubao-seedream-5-0-lite-260128",),
            ),
            Field("size", "Size", default="2K"),
            Field("watermark", "Watermark", "bool", default=False),
        ),
        advanced=("image", "response_format", "output_format", "callback_url", "async"),
    ),
    "happy_horse": Service(
        "happy_horse",
        "Happy Horse",
        "/happyhorse/videos",
        "/happyhorse/tasks",
        (
            Field("prompt", "Prompt", "multiline", required=True),
            Field(
                "model",
                "Model",
                default="happyhorse-1.1-t2v",
                options=("happyhorse-1.1-t2v",),
            ),
            Field("duration", "Duration (seconds)", "int", 3),
            Field("resolution", "Resolution", default="720P"),
            Field("ratio", "Aspect ratio", default="16:9"),
        ),
        fixed=(("action", "generate"),),
        advanced=("watermark", "callback_url", "async"),
    ),
    "qwen_image": Service(
        "qwen_image",
        "Qwen Image",
        "/qwen-image/images",
        "/qwen-image/tasks",
        (
            Field("prompt", "Prompt", "multiline", required=True),
            Field("model", "Model", default="qwen-image-3.0", options=("qwen-image-3.0",)),
            Field("n", "Image count", "int", 1),
            Field("size", "Size", default="1024*1024"),
        ),
        advanced=("negative_prompt", "seed", "watermark", "callback_url", "async"),
    ),
    "veo": Service(
        "veo",
        "Veo",
        "/veo/videos",
        "/veo/tasks",
        (
            Field("prompt", "Prompt", "multiline", required=True),
            Field("model", "Model", default="veo31-fast", options=("veo31-fast",)),
            Field("aspect_ratio", "Aspect ratio", default="16:9"),
        ),
        fixed=(("action", "text2video"),),
        advanced=("resolution", "callback_url", "async"),
    ),
    "google_search": Service(
        "google_search",
        "Google Search",
        "/serp/google",
        None,
        (
            Field("query", "Search query", required=True),
            Field(
                "type",
                "Search type",
                default="search",
                options=("search", "images", "news", "maps", "places", "videos"),
            ),
            Field("number", "Results", "int", 3),
            Field("page", "Page", "int", 1),
            Field("country", "Country"),
            Field("language", "Language"),
        ),
        advanced=("range", "image_size"),
    ),
    "grok": Service(
        "grok",
        "Grok Video",
        "/grok/videos",
        "/grok/tasks",
        (
            Field("prompt", "Prompt", "multiline", required=True),
            Field(
                "model",
                "Model",
                default="grok-imagine-video-1.5-fast:reverse",
                options=("grok-imagine-video-1.5-fast:reverse",),
            ),
            Field("duration", "Duration (seconds)", "int", 6),
            Field("resolution", "Resolution", default="480p"),
        ),
        advanced=("image_url", "aspect_ratio", "callback_url", "async"),
    ),
    "face_transform": Service(
        "face_transform",
        "Face Transform",
        "/face/analyze",
        None,
        (
            Field(
                "action",
                "Action",
                default="keypoints",
                options=(
                    "keypoints",
                    "beautify",
                    "age",
                    "gender",
                    "swap",
                    "cartoon",
                    "liveness",
                ),
            ),
            Field("image_url", "Image URL"),
            Field("source_image_url", "Source face URL"),
            Field("target_image_url", "Target image URL"),
        ),
        advanced=(
            "mode",
            "face_model_version",
            "need_rotate_detection",
            "age",
            "gender",
            "callback_url",
            "async",
        ),
    ),
    "midjourney": Service(
        "midjourney",
        "Midjourney",
        "/midjourney/imagine",
        "/midjourney/tasks",
        (
            Field("prompt", "Prompt", "multiline", required=True),
            Field("version", "Version", default="8.2"),
            Field("mode", "Mode", default="fast", options=("fast", "relax", "turbo")),
        ),
        fixed=(("action", "generate"),),
        advanced=("quality", "hd", "split_images", "callback_url", "async"),
    ),
    "flux": Service(
        "flux",
        "Flux",
        "/flux/images",
        "/flux/tasks",
        (
            Field("prompt", "Prompt", "multiline", required=True),
            Field("model", "Model", default="flux-dev", options=("flux-dev",)),
            Field("size", "Size", default="1024x1024"),
            Field("count", "Image count", "int", 1),
        ),
        fixed=(("action", "generate"),),
        advanced=("callback_url", "async"),
    ),
    "minimax_h3": Service(
        "minimax_h3",
        "MiniMax H3",
        "/minimax/videos",
        "/minimax/tasks",
        (
            Field("prompt", "Prompt", "multiline", required=True),
            Field("model", "Model", default="MiniMax-H3", options=("MiniMax-H3",)),
            Field("resolution", "Resolution", default="768P"),
            Field("duration", "Duration (seconds)", "int", 4),
            Field("ratio", "Aspect ratio", default="16:9"),
        ),
        advanced=("callback_url", "async"),
        prompt_as_content=True,
    ),
    "wan": Service(
        "wan",
        "Wan",
        "/wan/videos",
        "/wan/tasks",
        (
            Field("prompt", "Prompt", "multiline", required=True),
            Field("model", "Model", default="wan3.0-video", options=("wan3.0-video",)),
            Field("duration", "Duration (seconds)", "int", 5),
            Field("resolution", "Resolution", default="720P"),
            Field("ratio", "Aspect ratio", default="16:9"),
            Field("audio", "Generate audio", "bool", default=False),
        ),
        fixed=(("action", "text2video"),),
        advanced=("negative_prompt", "seed", "callback_url", "async"),
    ),
    "kling": Service(
        "kling",
        "Kling",
        "/kling/videos",
        "/kling/tasks",
        (
            Field("prompt", "Prompt", "multiline", required=True),
            Field("model", "Model", default="kling-v3-turbo", options=("kling-v3-turbo",)),
            Field("mode", "Mode", default="std", options=("std", "pro")),
            Field("duration", "Duration (seconds)", "int", 5),
            Field("aspect_ratio", "Aspect ratio", default="16:9"),
        ),
        fixed=(("action", "text2video"),),
        advanced=(
            "negative_prompt",
            "cfg_scale",
            "generate_audio",
            "callback_url",
            "async",
        ),
    ),
    "nano_banana": Service(
        "nano_banana",
        "Nano Banana",
        "/nano-banana/images",
        "/nano-banana/tasks",
        (
            Field("prompt", "Prompt", "multiline", required=True),
            Field(
                "model",
                "Model",
                default="nano-banana-2-lite",
                options=("nano-banana-2-lite",),
            ),
            Field("resolution", "Resolution", default="1K"),
            Field("aspect_ratio", "Aspect ratio", default="1:1"),
            Field("count", "Image count", "int", 1),
        ),
        fixed=(("action", "generate"),),
        advanced=("callback_url", "async"),
    ),
}

FACE_PATHS = {
    "keypoints": "/face/analyze",
    "beautify": "/face/beautify",
    "age": "/face/change-age",
    "gender": "/face/change-gender",
    "swap": "/face/swap",
    "cartoon": "/face/cartoon",
    "liveness": "/face/detect-live",
}
