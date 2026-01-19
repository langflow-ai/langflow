# Design Document: Content Blocks Support for Langflow Messages

**Author:** Claude
**Date:** January 2026
**Status:** Draft
**Version:** 1.0

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Background & Motivation](#background--motivation)
3. [Goals & Non-Goals](#goals--non-goals)
4. [Current Architecture](#current-architecture)
5. [Proposed Design](#proposed-design)
6. [Detailed Design](#detailed-design)
7. [Database Schema Changes](#database-schema-changes)
8. [Migration Strategy](#migration-strategy)
9. [API Changes](#api-changes)
10. [Backward Compatibility](#backward-compatibility)
11. [Testing Strategy](#testing-strategy)
12. [Rollout Plan](#rollout-plan)
13. [Open Questions](#open-questions)

---

## Executive Summary

This document proposes adding native support for the **content blocks message format** to Langflow, aligning with the modern message structure used by Anthropic's Claude API and LangChain 1.0. The implementation will be fully backward compatible, allowing existing flows and integrations to work without modification while enabling new multimodal and tool-use capabilities.

---

## Background & Motivation

### The Evolution of LLM Message Formats

Historically, LLM messages were simple text strings. As LLMs evolved to support multimodal inputs (images, audio, files) and tool use (function calling), the message format needed to evolve. The industry has converged on a **content blocks** format:

**Traditional Format (Legacy):**
```python
message = {"role": "user", "content": "Hello, world!"}
```

**Content Blocks Format (Modern):**
```python
message = {
    "role": "user",
    "content": [
        {"type": "text", "text": "What's in this image?"},
        {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "..."}}
    ]
}
```

### Anthropic's Content Blocks

Anthropic's Claude API uses content blocks for:

| Block Type | Purpose | Direction |
|------------|---------|-----------|
| `text` | Plain text content | Input/Output |
| `image` | Image data (base64 or URL) | Input |
| `tool_use` | Model requests to call a tool | Output |
| `tool_result` | Result of a tool call | Input |
| `document` | PDF/document content | Input |
| `thinking` | Extended thinking content | Output |

### LangChain 1.0 Alignment

LangChain 1.0 has adopted content blocks as the standard message format across all providers. The `content` field of `BaseMessage` can now be:
- `str` - Simple text (backward compatible)
- `list[dict]` - List of content blocks

```python
from langchain_core.messages import HumanMessage, AIMessage

# Legacy format (still works)
msg = HumanMessage(content="Hello")

# Content blocks format
msg = HumanMessage(content=[
    {"type": "text", "text": "Describe this image:"},
    {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}}
])
```

### Why Langflow Needs This

1. **Provider Compatibility**: Native support for Anthropic, OpenAI, and other providers' multimodal features
2. **Tool Use**: Proper representation of tool calls and results in conversation history
3. **LangChain 1.0**: Alignment with LangChain's message architecture
4. **Future-Proofing**: Support for emerging content types (audio, video, documents)

---

## Goals & Non-Goals

### Goals

1. **G1**: Support content blocks in the `Message` class with full type safety
2. **G2**: Maintain 100% backward compatibility with existing code using `text` field
3. **G3**: Enable seamless conversion between Langflow messages and LangChain messages
4. **G4**: Support all Anthropic content block types (text, image, tool_use, tool_result, document, thinking)
5. **G5**: Support OpenAI content block types (text, image_url, image_file)
6. **G6**: Persist content blocks to the database efficiently
7. **G7**: Display content blocks appropriately in the Langflow UI

### Non-Goals

- **NG1**: Real-time audio/video streaming (future work)
- **NG2**: Custom content block types defined by users
- **NG3**: Content block editing in the UI (read-only display initially)
- **NG4**: Breaking changes to existing APIs

---

## Current Architecture

### Message Class (`lfx/schema/message.py`)

The current `Message` class has:

```python
class Message(Data):
    text: str | AsyncIterator | Iterator | None  # Primary content
    sender: str | None
    sender_name: str | None
    files: list[str | Image] | None  # Multimodal support (limited)
    content_blocks: list[ContentBlock]  # Display-only blocks
    properties: Properties
    # ... other fields
```

**Current Limitations:**

1. **`text` is primary**: Content is stored in `text`, multimodal via `files`
2. **`content_blocks` is display-only**: Used for UI rendering, not LLM communication
3. **`files` handling is separate**: Images are processed separately from text
4. **No tool use representation**: Tool calls/results not properly modeled

### MessageTable (`services/database/models/message/model.py`)

```python
class MessageTable(MessageBase, table=True):
    text: str = Field(sa_column=Column(Text))
    files: list[str] = Field(sa_column=Column(JSON))
    content_blocks: list[dict | ContentBlock] = Field(sa_column=Column(JSON))
```

### Current Content Types (`schema/content_types.py`)

Langflow already has content types, but they're UI-focused:

- `TextContent` - Display text
- `MediaContent` - Display media URLs
- `CodeContent` - Display code with syntax highlighting
- `ToolContent` - Display tool calls (UI only)
- `ErrorContent` - Display errors
- `JSONContent` - Display JSON data

---

## Proposed Design

### Core Principle: Dual Representation

The `Message` class will support two representations of content:

1. **`text` + `files`** (Legacy): For backward compatibility
2. **`content`** (Modern): List of content blocks for full fidelity

These will be kept in sync through smart getters/setters.

### New Content Block Types

We'll add provider-agnostic content block types that map to both Anthropic and OpenAI formats:

```python
# New file: lfx/schema/llm_content.py

class LLMContentBlock(BaseModel):
    """Base class for LLM content blocks."""
    type: str

class TextBlock(LLMContentBlock):
    """Plain text content."""
    type: Literal["text"] = "text"
    text: str

class ImageBlock(LLMContentBlock):
    """Image content."""
    type: Literal["image"] = "image"
    source: ImageSource  # Supports base64 and URL

class ToolUseBlock(LLMContentBlock):
    """Tool/function call from the model."""
    type: Literal["tool_use"] = "tool_use"
    id: str
    name: str
    input: dict[str, Any]

class ToolResultBlock(LLMContentBlock):
    """Result of a tool call."""
    type: Literal["tool_result"] = "tool_result"
    tool_use_id: str
    content: str | list[LLMContentBlock]
    is_error: bool = False

class DocumentBlock(LLMContentBlock):
    """Document content (PDF, etc.)."""
    type: Literal["document"] = "document"
    source: DocumentSource

class ThinkingBlock(LLMContentBlock):
    """Extended thinking content (Anthropic)."""
    type: Literal["thinking"] = "thinking"
    thinking: str
```

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        Message Class                             │
├─────────────────────────────────────────────────────────────────┤
│  text: str | None           ←──┐                                │
│  files: list[str|Image]     ←──┼── Legacy Interface             │
│                                │   (Backward Compatible)        │
├────────────────────────────────┴────────────────────────────────┤
│  content: list[LLMContentBlock]  ← Modern Interface              │
│                                    (Full Fidelity)              │
├─────────────────────────────────────────────────────────────────┤
│  content_blocks: list[ContentBlock] ← UI Display Blocks         │
│  properties: Properties             ← UI Properties             │
└─────────────────────────────────────────────────────────────────┘
           │                                    │
           │ to_lc_message()                    │ from_lc_message()
           ▼                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                    LangChain BaseMessage                         │
├─────────────────────────────────────────────────────────────────┤
│  content: str | list[dict]                                      │
│  tool_calls: list[ToolCall]  (AIMessage only)                   │
│  tool_call_id: str           (ToolMessage only)                 │
└─────────────────────────────────────────────────────────────────┘
           │                                    │
           │ Provider-specific                  │
           ▼                                    ▼
┌──────────────────────┐         ┌──────────────────────┐
│   Anthropic API      │         │    OpenAI API        │
│   Content Blocks     │         │    Content Blocks    │
└──────────────────────┘         └──────────────────────┘
```

---

## Detailed Design

### 1. New Content Block Schema

**File: `lfx/schema/llm_content.py`**

```python
from __future__ import annotations

from typing import Annotated, Any, Literal, Union
from pydantic import BaseModel, Field, Discriminator, Tag

# === Image Sources ===

class Base64ImageSource(BaseModel):
    """Base64-encoded image data."""
    type: Literal["base64"] = "base64"
    media_type: str  # e.g., "image/png", "image/jpeg"
    data: str  # Base64-encoded bytes

class URLImageSource(BaseModel):
    """URL reference to an image."""
    type: Literal["url"] = "url"
    url: str

ImageSource = Annotated[
    Base64ImageSource | URLImageSource,
    Discriminator("type")
]

# === Document Sources ===

class Base64DocumentSource(BaseModel):
    """Base64-encoded document."""
    type: Literal["base64"] = "base64"
    media_type: str  # e.g., "application/pdf"
    data: str

class URLDocumentSource(BaseModel):
    """URL reference to a document."""
    type: Literal["url"] = "url"
    url: str

DocumentSource = Annotated[
    Base64DocumentSource | URLDocumentSource,
    Discriminator("type")
]

# === Content Blocks ===

class TextBlock(BaseModel):
    """Plain text content block."""
    type: Literal["text"] = "text"
    text: str

    @classmethod
    def from_string(cls, text: str) -> "TextBlock":
        return cls(text=text)

class ImageBlock(BaseModel):
    """Image content block."""
    type: Literal["image"] = "image"
    source: ImageSource

    @classmethod
    def from_base64(cls, data: str, media_type: str = "image/png") -> "ImageBlock":
        return cls(source=Base64ImageSource(media_type=media_type, data=data))

    @classmethod
    def from_url(cls, url: str) -> "ImageBlock":
        return cls(source=URLImageSource(url=url))

class ToolUseBlock(BaseModel):
    """Tool/function call from the model."""
    type: Literal["tool_use"] = "tool_use"
    id: str
    name: str
    input: dict[str, Any] = Field(default_factory=dict)

class ToolResultBlock(BaseModel):
    """Result of a tool call."""
    type: Literal["tool_result"] = "tool_result"
    tool_use_id: str
    content: str | list["LLMContentBlock"] = ""
    is_error: bool = False

class DocumentBlock(BaseModel):
    """Document content block (PDF, etc.)."""
    type: Literal["document"] = "document"
    source: DocumentSource
    title: str | None = None

class ThinkingBlock(BaseModel):
    """Extended thinking content (Anthropic)."""
    type: Literal["thinking"] = "thinking"
    thinking: str

# === Union Type with Discriminator ===

def _get_block_type(v: Any) -> str:
    if isinstance(v, dict):
        return v.get("type", "text")
    return getattr(v, "type", "text")

LLMContentBlock = Annotated[
    Annotated[TextBlock, Tag("text")]
    | Annotated[ImageBlock, Tag("image")]
    | Annotated[ToolUseBlock, Tag("tool_use")]
    | Annotated[ToolResultBlock, Tag("tool_result")]
    | Annotated[DocumentBlock, Tag("document")]
    | Annotated[ThinkingBlock, Tag("thinking")],
    Discriminator(_get_block_type)
]

# Type alias for content field
ContentList = list[LLMContentBlock]
```

### 2. Enhanced Message Class

**File: `lfx/schema/message.py` (modifications)**

```python
class Message(Data):
    """Message schema for Langflow.

    Content Representation:
    - For backward compatibility, `text` and `files` remain the primary interface
    - The new `content` field provides full content block support
    - These are kept in sync: setting `text` updates `content` and vice versa

    Usage:
        # Legacy way (still works)
        msg = Message(text="Hello", files=["image.png"])

        # Modern way (full control)
        msg = Message(content=[
            TextBlock(text="What's in this image?"),
            ImageBlock.from_file("image.png")
        ])

        # Mixed (content takes precedence)
        msg = Message(
            text="fallback",  # Used if content is empty
            content=[TextBlock(text="actual content")]
        )
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # === Legacy Fields (Backward Compatible) ===
    text_key: str = "text"
    text: str | AsyncIterator | Iterator | None = Field(default="")
    files: list[str | Image] | None = Field(default=[])

    # === Modern Content Blocks ===
    content: list[LLMContentBlock] = Field(default_factory=list)

    # === Other Fields (unchanged) ===
    sender: str | None = None
    sender_name: str | None = None
    session_id: str | UUID | None = Field(default="")
    # ... rest of fields

    def model_post_init(self, /, _context: Any) -> None:
        """Synchronize text/files with content blocks."""
        super().model_post_init(_context)
        self._sync_content()

    def _sync_content(self) -> None:
        """Ensure text/files and content are synchronized.

        Priority:
        1. If `content` is explicitly set and non-empty, it's authoritative
        2. Otherwise, build `content` from `text` and `files`
        """
        if self.content:
            # Content is authoritative - update text for backward compat
            self._update_text_from_content()
        elif self.text or self.files:
            # Build content from legacy fields
            self._update_content_from_text_files()

    def _update_text_from_content(self) -> None:
        """Extract text from content blocks for backward compatibility."""
        text_parts = []
        for block in self.content:
            if isinstance(block, TextBlock):
                text_parts.append(block.text)
        if text_parts and not self.text:
            self.text = "\n".join(text_parts)

    def _update_content_from_text_files(self) -> None:
        """Build content blocks from text and files."""
        blocks: list[LLMContentBlock] = []

        # Add text block if present
        if self.text and isinstance(self.text, str):
            blocks.append(TextBlock(text=self.text))

        # Add image blocks from files
        for file in self.files or []:
            if isinstance(file, Image):
                blocks.append(self._image_to_block(file))
            elif isinstance(file, str) and is_image_file(file):
                blocks.append(self._file_to_image_block(file))

        self.content = blocks

    def _image_to_block(self, image: Image) -> ImageBlock:
        """Convert Image object to ImageBlock."""
        if image.url:
            return ImageBlock.from_url(image.url)
        elif image.path:
            base64_data = image.to_base64()
            media_type = self._get_media_type(image.path)
            return ImageBlock.from_base64(base64_data, media_type)
        raise ValueError("Image must have either url or path")

    @staticmethod
    def _get_media_type(path: str) -> str:
        """Get MIME type from file path."""
        ext = path.lower().rsplit(".", 1)[-1]
        return {
            "png": "image/png",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "gif": "image/gif",
            "webp": "image/webp",
        }.get(ext, "image/png")

    # === Enhanced LangChain Conversion ===

    def to_lc_message(self, model_name: str | None = None) -> BaseMessage:
        """Convert to LangChain message with content blocks support.

        Args:
            model_name: Optional model name for provider-specific formatting

        Returns:
            LangChain BaseMessage with appropriate content structure
        """
        # Determine message type based on sender
        if self.sender == MESSAGE_SENDER_USER or not self.sender:
            return self._to_human_message(model_name)
        elif self.sender == MESSAGE_SENDER_AI:
            return self._to_ai_message(model_name)
        elif self.sender == "Tool":
            return self._to_tool_message()
        else:
            # Default to human message
            return self._to_human_message(model_name)

    def _to_human_message(self, model_name: str | None = None) -> HumanMessage:
        """Convert to HumanMessage with content blocks."""
        content = self._content_to_lc_format(model_name)
        return HumanMessage(content=content)

    def _to_ai_message(self, model_name: str | None = None) -> AIMessage:
        """Convert to AIMessage with tool calls if present."""
        content = self._content_to_lc_format(model_name)

        # Extract tool calls
        tool_calls = []
        for block in self.content:
            if isinstance(block, ToolUseBlock):
                tool_calls.append({
                    "id": block.id,
                    "name": block.name,
                    "args": block.input,
                })

        if tool_calls:
            return AIMessage(content=content, tool_calls=tool_calls)
        return AIMessage(content=content)

    def _to_tool_message(self) -> ToolMessage:
        """Convert to ToolMessage."""
        # Find tool result block
        for block in self.content:
            if isinstance(block, ToolResultBlock):
                content = block.content if isinstance(block.content, str) else str(block.content)
                return ToolMessage(
                    content=content,
                    tool_call_id=block.tool_use_id,
                )

        # Fallback to text
        return ToolMessage(
            content=self.text or "",
            tool_call_id="",
        )

    def _content_to_lc_format(self, model_name: str | None = None) -> str | list[dict]:
        """Convert content blocks to LangChain format.

        Returns:
            - str if content is simple text
            - list[dict] if content has multiple blocks or non-text content
        """
        if not self.content:
            return self.text or ""

        # Check if content is simple text only
        if len(self.content) == 1 and isinstance(self.content[0], TextBlock):
            return self.content[0].text

        # Convert to list of dicts
        lc_content = []
        for block in self.content:
            lc_content.append(self._block_to_lc_dict(block, model_name))

        return lc_content

    def _block_to_lc_dict(self, block: LLMContentBlock, model_name: str | None) -> dict:
        """Convert a content block to LangChain dict format."""
        if isinstance(block, TextBlock):
            return {"type": "text", "text": block.text}

        elif isinstance(block, ImageBlock):
            # Format depends on provider
            if model_name and "claude" in model_name.lower():
                return self._image_block_to_anthropic(block)
            else:
                return self._image_block_to_openai(block)

        elif isinstance(block, ToolUseBlock):
            return {
                "type": "tool_use",
                "id": block.id,
                "name": block.name,
                "input": block.input,
            }

        elif isinstance(block, ToolResultBlock):
            return {
                "type": "tool_result",
                "tool_use_id": block.tool_use_id,
                "content": block.content,
                "is_error": block.is_error,
            }

        elif isinstance(block, DocumentBlock):
            return {
                "type": "document",
                "source": block.source.model_dump(),
            }

        elif isinstance(block, ThinkingBlock):
            return {
                "type": "thinking",
                "thinking": block.thinking,
            }

        # Fallback
        return block.model_dump()

    def _image_block_to_anthropic(self, block: ImageBlock) -> dict:
        """Convert ImageBlock to Anthropic format."""
        if isinstance(block.source, URLImageSource):
            return {
                "type": "image",
                "source": {
                    "type": "url",
                    "url": block.source.url,
                }
            }
        else:
            return {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": block.source.media_type,
                    "data": block.source.data,
                }
            }

    def _image_block_to_openai(self, block: ImageBlock) -> dict:
        """Convert ImageBlock to OpenAI format."""
        if isinstance(block.source, URLImageSource):
            url = block.source.url
        else:
            # Convert base64 to data URL
            url = f"data:{block.source.media_type};base64,{block.source.data}"

        return {
            "type": "image_url",
            "image_url": {"url": url}
        }

    @classmethod
    def from_lc_message(cls, lc_message: BaseMessage) -> "Message":
        """Create Message from LangChain message with content blocks support."""
        # Determine sender
        sender, sender_name = cls._get_sender_from_lc_type(lc_message.type)

        # Parse content
        content_blocks = cls._parse_lc_content(lc_message.content)

        # Handle tool calls in AIMessage
        if hasattr(lc_message, "tool_calls") and lc_message.tool_calls:
            for tc in lc_message.tool_calls:
                content_blocks.append(ToolUseBlock(
                    id=tc.get("id", ""),
                    name=tc.get("name", ""),
                    input=tc.get("args", {}),
                ))

        # Handle ToolMessage
        if lc_message.type == "tool" and hasattr(lc_message, "tool_call_id"):
            content_blocks = [ToolResultBlock(
                tool_use_id=lc_message.tool_call_id,
                content=lc_message.content if isinstance(lc_message.content, str) else str(lc_message.content),
            )]

        # Extract text for backward compatibility
        text = cls._extract_text_from_content(content_blocks)

        return cls(
            text=text,
            content=content_blocks,
            sender=sender,
            sender_name=sender_name,
        )

    @staticmethod
    def _get_sender_from_lc_type(msg_type: str) -> tuple[str, str]:
        """Map LangChain message type to sender info."""
        mapping = {
            "human": (MESSAGE_SENDER_USER, MESSAGE_SENDER_NAME_USER),
            "ai": (MESSAGE_SENDER_AI, MESSAGE_SENDER_NAME_AI),
            "system": ("System", "System"),
            "tool": ("Tool", "Tool"),
        }
        return mapping.get(msg_type, (msg_type, msg_type))

    @classmethod
    def _parse_lc_content(cls, content: str | list) -> list[LLMContentBlock]:
        """Parse LangChain content to content blocks."""
        if isinstance(content, str):
            return [TextBlock(text=content)] if content else []

        blocks = []
        for item in content:
            if isinstance(item, str):
                blocks.append(TextBlock(text=item))
            elif isinstance(item, dict):
                blocks.append(cls._dict_to_block(item))

        return blocks

    @classmethod
    def _dict_to_block(cls, d: dict) -> LLMContentBlock:
        """Convert a dict to appropriate content block."""
        block_type = d.get("type", "text")

        if block_type == "text":
            return TextBlock(text=d.get("text", ""))

        elif block_type in ("image", "image_url"):
            return cls._parse_image_dict(d)

        elif block_type == "tool_use":
            return ToolUseBlock(
                id=d.get("id", ""),
                name=d.get("name", ""),
                input=d.get("input", {}),
            )

        elif block_type == "tool_result":
            return ToolResultBlock(
                tool_use_id=d.get("tool_use_id", ""),
                content=d.get("content", ""),
                is_error=d.get("is_error", False),
            )

        elif block_type == "thinking":
            return ThinkingBlock(thinking=d.get("thinking", ""))

        # Default to text
        return TextBlock(text=str(d))

    @classmethod
    def _parse_image_dict(cls, d: dict) -> ImageBlock:
        """Parse image dict from various formats."""
        # OpenAI format
        if "image_url" in d:
            url = d["image_url"].get("url", "")
            if url.startswith("data:"):
                # Parse data URL
                parts = url.split(",", 1)
                media_type = parts[0].replace("data:", "").replace(";base64", "")
                data = parts[1] if len(parts) > 1 else ""
                return ImageBlock.from_base64(data, media_type)
            return ImageBlock.from_url(url)

        # Anthropic format
        if "source" in d:
            source = d["source"]
            if source.get("type") == "base64":
                return ImageBlock.from_base64(
                    source.get("data", ""),
                    source.get("media_type", "image/png"),
                )
            elif source.get("type") == "url":
                return ImageBlock.from_url(source.get("url", ""))

        # Fallback
        return ImageBlock.from_url(d.get("url", ""))

    @staticmethod
    def _extract_text_from_content(blocks: list[LLMContentBlock]) -> str:
        """Extract text content for backward compatibility."""
        text_parts = []
        for block in blocks:
            if isinstance(block, TextBlock):
                text_parts.append(block.text)
        return "\n".join(text_parts)
```

### 3. Provider-Specific Formatting

**File: `lfx/schema/llm_content_formatters.py`**

```python
"""Provider-specific content block formatters."""

from typing import Protocol
from lfx.schema.llm_content import LLMContentBlock, TextBlock, ImageBlock, ToolUseBlock

class ContentFormatter(Protocol):
    """Protocol for provider-specific content formatting."""

    def format_content(self, blocks: list[LLMContentBlock]) -> list[dict]:
        """Format content blocks for the provider."""
        ...

class AnthropicFormatter:
    """Format content blocks for Anthropic Claude API."""

    def format_content(self, blocks: list[LLMContentBlock]) -> list[dict]:
        result = []
        for block in blocks:
            result.append(self._format_block(block))
        return result

    def _format_block(self, block: LLMContentBlock) -> dict:
        if isinstance(block, TextBlock):
            return {"type": "text", "text": block.text}
        elif isinstance(block, ImageBlock):
            return {
                "type": "image",
                "source": block.source.model_dump()
            }
        elif isinstance(block, ToolUseBlock):
            return {
                "type": "tool_use",
                "id": block.id,
                "name": block.name,
                "input": block.input,
            }
        return block.model_dump()

class OpenAIFormatter:
    """Format content blocks for OpenAI API."""

    def format_content(self, blocks: list[LLMContentBlock]) -> list[dict]:
        result = []
        for block in blocks:
            result.append(self._format_block(block))
        return result

    def _format_block(self, block: LLMContentBlock) -> dict:
        if isinstance(block, TextBlock):
            return {"type": "text", "text": block.text}
        elif isinstance(block, ImageBlock):
            # OpenAI uses image_url format
            if hasattr(block.source, "url"):
                url = block.source.url
            else:
                url = f"data:{block.source.media_type};base64,{block.source.data}"
            return {
                "type": "image_url",
                "image_url": {"url": url}
            }
        return block.model_dump()

def get_formatter(model_name: str | None) -> ContentFormatter:
    """Get the appropriate formatter for a model."""
    if model_name:
        name_lower = model_name.lower()
        if "claude" in name_lower or "anthropic" in name_lower:
            return AnthropicFormatter()
        if "gpt" in name_lower or "o1" in name_lower:
            return OpenAIFormatter()

    # Default to OpenAI format (most widely supported)
    return OpenAIFormatter()
```

---

## Database Schema Changes

### MessageTable Updates

**File: `services/database/models/message/model.py`**

```python
class MessageBase(SQLModel):
    # ... existing fields ...

    # New field for LLM content blocks
    content: list[dict] = Field(
        default_factory=list,
        sa_column=Column(JSON),
        description="LLM content blocks (text, images, tool calls, etc.)"
    )

    # Existing content_blocks renamed for clarity
    display_blocks: list[dict | ContentBlock] = Field(
        default_factory=list,
        sa_column=Column(JSON),
        description="UI display blocks (for rendering)"
    )

    @classmethod
    def from_message(cls, message: "Message", flow_id: str | UUID | None = None):
        # ... existing logic ...

        # Serialize LLM content blocks
        content = []
        for block in message.content or []:
            if hasattr(block, "model_dump"):
                content.append(block.model_dump())
            else:
                content.append(block)

        return cls(
            # ... existing fields ...
            content=content,
            display_blocks=display_blocks,  # renamed from content_blocks
        )
```

### Database Migration

```python
"""Add content column to message table.

Revision ID: add_content_blocks
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

def upgrade():
    # Add new content column
    op.add_column(
        'message',
        sa.Column('content', sa.JSON(), nullable=True, default=[])
    )

    # Migrate existing data: convert text to content blocks
    op.execute("""
        UPDATE message
        SET content = json_build_array(
            json_build_object('type', 'text', 'text', COALESCE(text, ''))
        )
        WHERE content IS NULL
    """)

    # Rename content_blocks to display_blocks (optional, for clarity)
    # op.alter_column('message', 'content_blocks', new_column_name='display_blocks')

def downgrade():
    op.drop_column('message', 'content')
```

---

## API Changes

### REST API

No breaking changes. New fields are additive:

```python
# GET /api/v1/messages/{session_id}
{
    "id": "uuid",
    "text": "Hello!",  # Backward compatible
    "content": [       # New field
        {"type": "text", "text": "Hello!"}
    ],
    "sender": "User",
    "files": [],
    # ... other fields
}
```

### WebSocket Events

Message events will include content blocks:

```python
{
    "type": "message",
    "message": {
        "text": "What's in this image?",
        "content": [
            {"type": "text", "text": "What's in this image?"},
            {"type": "image", "source": {"type": "base64", ...}}
        ],
        "files": ["image.png"],  # Backward compatible
        # ...
    }
}
```

---

## Backward Compatibility

### Compatibility Matrix

| Scenario | Behavior |
|----------|----------|
| Old code uses `message.text` | Works - text field always populated |
| Old code uses `message.files` | Works - files field preserved |
| Old code calls `to_lc_message()` | Works - returns proper LangChain message |
| Old code stores message | Works - both text and content stored |
| New code uses `message.content` | Works - full content block access |
| Mix of old and new | Works - fields synchronized |

### Migration Path

1. **Phase 1**: Add `content` field alongside existing fields
2. **Phase 2**: Components can start using content blocks
3. **Phase 3**: UI updated to render content blocks
4. **Phase 4**: (Future) Deprecate `files` field in favor of content blocks

### Deprecation Warnings

```python
class Message(Data):
    @property
    def files(self) -> list[str | Image] | None:
        # Future: Add deprecation warning
        # warnings.warn(
        #     "Message.files is deprecated. Use Message.content with ImageBlock instead.",
        #     DeprecationWarning,
        #     stacklevel=2
        # )
        return self._files
```

---

## Testing Strategy

### Unit Tests

```python
# tests/unit/schema/test_llm_content.py

class TestTextBlock:
    def test_create_text_block(self):
        block = TextBlock(text="Hello")
        assert block.type == "text"
        assert block.text == "Hello"

    def test_from_string(self):
        block = TextBlock.from_string("Hello")
        assert block.text == "Hello"

class TestImageBlock:
    def test_from_base64(self):
        block = ImageBlock.from_base64("abc123", "image/png")
        assert block.type == "image"
        assert block.source.data == "abc123"

    def test_from_url(self):
        block = ImageBlock.from_url("https://example.com/image.png")
        assert block.source.url == "https://example.com/image.png"

class TestMessageContentBlocks:
    def test_legacy_text_creates_content(self):
        msg = Message(text="Hello")
        assert len(msg.content) == 1
        assert isinstance(msg.content[0], TextBlock)
        assert msg.content[0].text == "Hello"

    def test_content_updates_text(self):
        msg = Message(content=[TextBlock(text="Hello")])
        assert msg.text == "Hello"

    def test_multimodal_message(self):
        msg = Message(content=[
            TextBlock(text="What's this?"),
            ImageBlock.from_url("https://example.com/img.png")
        ])
        assert msg.text == "What's this?"
        assert len(msg.content) == 2

class TestLangChainConversion:
    def test_to_human_message_simple(self):
        msg = Message(text="Hello", sender="User")
        lc_msg = msg.to_lc_message()
        assert isinstance(lc_msg, HumanMessage)
        assert lc_msg.content == "Hello"

    def test_to_human_message_multimodal(self):
        msg = Message(
            sender="User",
            content=[
                TextBlock(text="What's this?"),
                ImageBlock.from_url("https://example.com/img.png")
            ]
        )
        lc_msg = msg.to_lc_message()
        assert isinstance(lc_msg.content, list)
        assert len(lc_msg.content) == 2

    def test_from_lc_message_with_tool_calls(self):
        lc_msg = AIMessage(
            content="I'll help you.",
            tool_calls=[{"id": "1", "name": "search", "args": {"q": "test"}}]
        )
        msg = Message.from_lc_message(lc_msg)
        assert any(isinstance(b, ToolUseBlock) for b in msg.content)
```

### Integration Tests

```python
# tests/integration/test_content_blocks_flow.py

class TestContentBlocksIntegration:
    async def test_anthropic_multimodal_flow(self, client):
        """Test sending image to Claude."""
        # Create flow with Anthropic component
        # Send message with image
        # Verify response
        pass

    async def test_tool_use_roundtrip(self, client):
        """Test tool calls are preserved through the system."""
        # Create flow with tool-enabled model
        # Trigger tool call
        # Verify tool_use and tool_result blocks
        pass

    async def test_database_persistence(self, client):
        """Test content blocks are stored and retrieved correctly."""
        msg = Message(content=[
            TextBlock(text="Hello"),
            ImageBlock.from_base64("abc", "image/png")
        ])
        # Store and retrieve
        # Verify content blocks preserved
        pass
```

---

## Rollout Plan

### Phase 1: Foundation
- Add `LLMContentBlock` types
- Add `content` field to `Message` class
- Implement synchronization between `text`/`files` and `content`
- Add database column

### Phase 2: LangChain Integration
- Update `to_lc_message()` to use content blocks
- Update `from_lc_message()` to parse content blocks
- Add provider-specific formatters

### Phase 3: Component Updates
- Update Anthropic component to leverage content blocks
- Update OpenAI component
- Update other LLM components

### Phase 4: UI Updates
- Update message display to render content blocks
- Add support for displaying tool calls
- Add support for displaying images inline

### Phase 5: Advanced Features
- Extended thinking display
- Document blocks
- Tool result rendering

---

## Open Questions

1. **Display Block Naming**: Should we rename `content_blocks` to `display_blocks` to avoid confusion with LLM `content`?

2. **Streaming**: How should streaming work with content blocks? Currently `text` can be an `AsyncIterator`.

3. **Tool Result Content**: Should `ToolResultBlock.content` support nested content blocks or just strings?

4. **Cache Control**: Anthropic supports cache control on content blocks. Should we support this?

5. **Audio/Video**: Should we add `AudioBlock` and `VideoBlock` types now or wait?

---

## Appendix A: Provider Format Comparison

### Anthropic Format

```json
{
    "role": "user",
    "content": [
        {"type": "text", "text": "What's in this image?"},
        {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": "..."
            }
        }
    ]
}
```

### OpenAI Format

```json
{
    "role": "user",
    "content": [
        {"type": "text", "text": "What's in this image?"},
        {
            "type": "image_url",
            "image_url": {
                "url": "data:image/png;base64,..."
            }
        }
    ]
}
```

### LangChain Format

```python
HumanMessage(content=[
    {"type": "text", "text": "What's in this image?"},
    {"type": "image_url", "image_url": {"url": "..."}}
])
```

---

## Appendix B: Full Type Definitions

See `lfx/schema/llm_content.py` for complete type definitions with all fields and validators.
