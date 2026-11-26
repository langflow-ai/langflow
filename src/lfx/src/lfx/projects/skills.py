"""Portable skill definitions and reviewed packs, independent of application storage."""

from __future__ import annotations

import hashlib
import json
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from lfx.projects.bindings import compose_single_binding
from lfx.projects.tool_packs import ToolPackReference

SKILLS_ORIGIN = "_harness_skills"
MAX_SKILLS = 50
MAX_SKILL_PACKS = 50


class SkillDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    description: str = Field(min_length=1, max_length=1024)
    instructions: str = Field(min_length=1, max_length=50000)
    tool_packs: tuple[ToolPackReference, ...] = ()

    @field_validator("description", "instructions")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            msg = "A skill needs a description and instructions."
            raise ValueError(msg)
        return value

    @field_validator("tool_packs")
    @classmethod
    def unique_tools(cls, value):
        if len({ref.project_id for ref in value}) != len(value):
            msg = "Select each Tool Pack once per skill."
            raise ValueError(msg)
        return value


def skill_definitions(value: object) -> tuple[SkillDefinition, ...]:
    if not isinstance(value, (list, tuple)) or len(value) > MAX_SKILLS:
        msg = "A Skill Pack supports up to 50 skills."
        raise ValueError(msg)
    skills = tuple(SkillDefinition.model_validate(item) for item in value)
    if len({skill.name for skill in skills}) != len(skills):
        msg = "Skill names must be unique within a pack."
        raise ValueError(msg)
    return skills


class SkillPackReference(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    project_id: UUID
    expected_type: Literal["skill-pack"] = "skill-pack"
    revision: str = Field(pattern=r"^[a-f0-9]{64}$")


class SkillPackManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    reference: SkillPackReference
    name: str
    skills: tuple[SkillDefinition, ...]

    @model_validator(mode="after")
    def validate_revision(self):
        skill_definitions(self.skills)
        if self.reference.revision != skill_pack_revision(self.name, self.skills):
            msg = "Skill Pack revision does not match its content."
            raise ValueError(msg)
        return self


def skill_pack_revision(name: str, skills: tuple[SkillDefinition, ...]) -> str:
    payload = {"name": name, "skills": [skill.model_dump(mode="json") for skill in skills]}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def skill_pack_manifest(project_id: UUID, name: str, config: dict | None) -> SkillPackManifest:
    skills = skill_definitions((config or {}).get("skills", []))
    return SkillPackManifest(
        reference=SkillPackReference(project_id=project_id, revision=skill_pack_revision(name, skills)),
        name=name,
        skills=skills,
    )


def skill_pack_references(value: object) -> tuple[SkillPackReference, ...]:
    if not isinstance(value, list) or len(value) > MAX_SKILL_PACKS:
        msg = "Choose up to 50 Skill Packs."
        raise ValueError(msg)
    references = tuple(SkillPackReference.model_validate(item) for item in value)
    if len({ref.project_id for ref in references}) != len(references):
        msg = "Select each Skill Pack once."
        raise ValueError(msg)
    return references


class HarnessSkills(BaseModel):
    """Content is copied at explicit review; subsequent edits never replace it during a run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    packs: tuple[SkillPackManifest, ...] = ()
    global_tool_pack_ids: tuple[UUID, ...] = ()

    @model_validator(mode="after")
    def unique_packs(self):
        if len({pack.reference.project_id for pack in self.packs}) != len(self.packs):
            msg = "Select each Skill Pack once."
            raise ValueError(msg)
        return self


def parse_harness_skills(value: str) -> HarnessSkills:
    return HarnessSkills.model_validate_json(value) if value.strip() not in {"", "null", "{}"} else HarnessSkills()


def compose_skills(data: dict, *, project_id: str, agent_id: str, skills: HarnessSkills) -> dict:
    return compose_single_binding(
        data,
        project_id=project_id,
        agent_id=agent_id,
        binding=skills if skills.packs else None,
        input_name="skill_bindings",
        origin_name=SKILLS_ORIGIN,
        label="Skills",
    )
