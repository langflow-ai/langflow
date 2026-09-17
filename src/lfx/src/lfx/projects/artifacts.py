"""Sourced reports keep captured evidence separate from generated prose.

``[@source-id]`` markers resolve against the supplied evidence, never against
URLs invented in the report. Resolution is a membership check, not an
assessment of whether the evidence supports a claim. Nothing here fetches URLs.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Literal
from urllib.parse import quote, urlsplit
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

if TYPE_CHECKING:
    from lfx.services.storage.service import StorageService

_CITATION = re.compile(r"\[@([^\]\r\n]*)\]")
SOURCE_EVIDENCE_KIND = "lfx.source_evidence"


class SourceRecord(BaseModel):
    """The exact text supplied by a retrieval step, including explicit failure.

    Identity covers the location and captured material. A changed page gets a
    new ID; repeating the same capture does not invalidate existing citations.
    It does not authenticate the publisher or the component supplying the text.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = ""
    uri: str = Field(min_length=1)
    title: str = Field(min_length=1)
    content: str = ""
    availability: Literal["available", "unavailable"] = "available"
    unavailable_reason: str = ""
    captured_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("captured_at")
    @classmethod
    def aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            msg = "Source capture time must include a timezone."
            raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def validate_capture(self) -> SourceRecord:
        if self.availability == "available":
            if not self.content.strip() or self.unavailable_reason:
                msg = "Available evidence needs captured text and no unavailable reason."
                raise ValueError(msg)
        elif self.content or not self.unavailable_reason.strip():
            msg = "Unavailable evidence needs a reason and must not claim captured text."
            raise ValueError(msg)
        payload = json.dumps(
            [self.uri, self.title, self.content, self.availability, self.unavailable_reason],
            ensure_ascii=False,
            separators=(",", ":"),
        )
        identity = "source-" + hashlib.sha256(payload.encode()).hexdigest()[:24]
        if self.id and self.id != identity:
            msg = "Source ID does not match its captured evidence."
            raise ValueError(msg)
        object.__setattr__(self, "id", identity)
        return self


class ArtifactExecution(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    flow_id: UUID
    run_id: UUID
    node_id: str = Field(min_length=1)


class CitationResolution(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: str
    status: Literal["resolved", "unavailable", "missing"]


class SourceUse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: str
    tool_call_id: str = Field(min_length=1)
    tool_name: str | None = None


class CollectedEvidence(BaseModel):
    """Evidence retained in agent state independently of compacted messages."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    sources: tuple[SourceRecord, ...] = ()
    uses: tuple[SourceUse, ...] = ()

    @model_validator(mode="after")
    def validate_references(self) -> CollectedEvidence:
        ids = {source.id for source in self.sources}
        if any(use.source_id not in ids for use in self.uses):
            msg = "Source use refers to missing captured evidence."
            raise ValueError(msg)
        return self


class AgentRunResult(BaseModel):
    """The final answer and its evidence, separate from the streamed conversation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    answer: str
    evidence: CollectedEvidence


class SourcedReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    id: UUID = Field(default_factory=uuid4)
    title: str = Field(min_length=1)
    markdown: str = Field(min_length=1)
    execution: ArtifactExecution
    sources: tuple[SourceRecord, ...] = ()
    source_uses: tuple[SourceUse, ...] = ()
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    claim_support: Literal["not_evaluated"] = "not_evaluated"

    @model_validator(mode="after")
    def unique_sources(self) -> SourcedReport:
        seen: set[str] = set()
        sources = []
        for source in self.sources:
            if source.id not in seen:
                seen.add(source.id)
                sources.append(source)
        object.__setattr__(self, "sources", tuple(sources))
        CollectedEvidence(sources=self.sources, uses=self.source_uses)
        return self

    @property
    def citations(self) -> tuple[CitationResolution, ...]:
        sources = {source.id: source for source in self.sources}
        return tuple(
            CitationResolution(
                source_id=source_id,
                status=(
                    "missing"
                    if source_id not in sources
                    else "resolved"
                    if sources[source_id].availability == "available"
                    else "unavailable"
                ),
            )
            for source_id in dict.fromkeys(_CITATION.findall(self.markdown))
        )

    def require_resolved_citations(self) -> None:
        if not self.citations:
            msg = "The report needs at least one [@source-id] citation to captured evidence."
            raise ValueError(msg)
        if any(citation.status != "resolved" for citation in self.citations):
            msg = "The report cites missing or unavailable evidence. Inspect its source references before saving."
            raise ValueError(msg)

    def render_markdown(self) -> str:
        """Render a portable report with references into the accompanying evidence JSON."""
        citations = {item.source_id: index for index, item in enumerate(self.citations, 1)}
        body = _CITATION.sub(lambda match: f"[{citations[match[1]]}](#source-{citations[match[1]]})", self.markdown)
        lines = [f"# {_plain_title(self.title)}", "", body, "", "## Sources", ""]
        sources = {source.id: source for source in self.sources}
        if not citations:
            lines.append("No source citations were supplied.")
        for source_id, index in citations.items():
            source = sources.get(source_id)
            lines.extend([f"### Source {index}", ""])
            if source is None:
                lines.append(f"Evidence missing. Reference: {_plain_title(source_id)}.")
            else:
                title = _plain_title(source.title)
                link = _web_link(source.uri)
                lines.append(f"[{title}]({link})" if link else title)
                lines.append(f"\nEvidence ID: `{source.id}`. Captured: {source.captured_at.isoformat()}.")
                if source.availability == "unavailable":
                    lines.append(f"\nEvidence unavailable: {_plain_title(source.unavailable_reason)}")
            lines.append("")
        lines.extend(
            [
                "Citation resolution checks source membership only. Claim support has not been evaluated.",
                "The accompanying JSON preserves the captured evidence separately from this generated report.",
                "",
                f"Execution: `{self.execution.run_id}`. Flow: `{self.execution.flow_id}`.",
                "",
            ]
        )
        return "\n".join(lines)


def _plain_title(value: str) -> str:
    # Titles and error reasons are untrusted source text, not Markdown markup.
    return re.sub(r"([\\`*_{}\[\]()<>#!|])", r"\\\1", " ".join(value.split()))


def _web_link(uri: str) -> str | None:
    try:
        parsed = urlsplit(uri)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            return None
    except ValueError:
        return None
    return quote(uri, safe=":/?#@!$&'*+,;=%~_-")


class StoredReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    report: SourcedReport
    markdown_name: str
    record_name: str


class ReportSummary(BaseModel):
    """Small browsing record; original source text stays in the canonical report."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["sourced_report"] = "sourced_report"
    id: UUID
    title: str = Field(min_length=1)
    created_at: datetime
    execution: ArtifactExecution
    source_count: int = Field(ge=0)
    citation_count: int = Field(ge=0)
    unresolved_citation_count: int = Field(ge=0)
    citations_resolved: bool
    claim_support: Literal["not_evaluated"] = "not_evaluated"

    @field_validator("created_at")
    @classmethod
    def aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            msg = "Report creation time must include a timezone."
            raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def consistent_citations(self) -> ReportSummary:
        if self.unresolved_citation_count > self.citation_count or self.citations_resolved != (
            bool(self.citation_count) and not self.unresolved_citation_count
        ):
            msg = "Report citation counts are inconsistent."
            raise ValueError(msg)
        return self

    @classmethod
    def from_report(cls, report: SourcedReport) -> ReportSummary:
        citations = report.citations
        unresolved = sum(citation.status != "resolved" for citation in citations)
        return cls(
            id=report.id,
            title=report.title,
            created_at=report.created_at,
            execution=report.execution,
            source_count=len(report.sources),
            citation_count=len(citations),
            unresolved_citation_count=unresolved,
            citations_resolved=bool(citations) and not unresolved,
        )


async def store_report(report: SourcedReport, storage: StorageService) -> StoredReport:
    """Save unique immutable files; the JSON record is written last.

    Uses the existing flow storage namespace, so the host's file download route
    enforces the same flow access as other generated files. The returned names
    are storage basenames, not host URLs or local filesystem paths. Each save
    allocates a new artifact identity, including repeated/concurrent saves.
    """
    report = report.model_copy(update={"id": uuid4()})
    flow_id = str(report.execution.flow_id)
    markdown_name = f"report-{report.id}.md"
    record_name = f"report-{report.id}.json"
    summary_name = f"report-{report.id}.summary.json"
    try:
        await storage.save_file(flow_id, markdown_name, report.render_markdown().encode())
        await storage.save_file(flow_id, summary_name, ReportSummary.from_report(report).model_dump_json().encode())
        await storage.save_file(flow_id, record_name, report.model_dump_json(indent=2).encode())
    except Exception:
        # Names are unique to this artifact. Never remove another run's files.
        for name in (record_name, summary_name, markdown_name):
            with contextlib.suppress(Exception):
                await storage.delete_file(flow_id, name)
        raise
    return StoredReport(report=report, markdown_name=markdown_name, record_name=record_name)
