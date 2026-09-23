import type { ToolPackReference } from "@/controllers/API/queries/folders/use-project-tool-pack";

export type SkillDefinition = {
  name: string;
  description: string;
  instructions: string;
  tool_packs: ToolPackReference[];
};

export type SkillPackReference = {
  project_id: string;
  expected_type: "skill-pack";
  revision: string;
};

export type CapabilityReference = SkillPackReference | ToolPackReference;
export type SkillPackManifest = {
  reference: SkillPackReference;
  name: string;
  skills: SkillDefinition[];
};

export function validSkills(skills: SkillDefinition[]): boolean {
  return (
    skills.length <= 50 &&
    new Set(skills.map((skill) => skill.name)).size === skills.length &&
    skills.every(
      (skill) =>
        skill.name.length <= 64 &&
        /^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(skill.name) &&
        !!skill.description.trim() &&
        skill.description.length <= 1024 &&
        !!skill.instructions.trim() &&
        skill.instructions.length <= 50000,
    )
  );
}
