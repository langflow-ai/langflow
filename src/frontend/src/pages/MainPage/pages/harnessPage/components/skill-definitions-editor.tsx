import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import type { ToolPackReference } from "@/controllers/API/queries/folders/use-project-tool-pack";
import { type SkillDefinition, validSkills } from "../skills";
import { CapabilityPackPicker } from "./capability-pack-picker";

export function SkillDefinitionsEditor({
  value,
  disabled,
  projectId,
  onOpen,
  onChange,
}: {
  value: SkillDefinition[];
  disabled?: boolean;
  projectId: string;
  onOpen: () => void;
  onChange: (next: SkillDefinition[]) => void;
}) {
  const { t } = useTranslation();
  const update = (index: number, changes: Partial<SkillDefinition>) =>
    onChange(
      value.map((skill, i) => (i === index ? { ...skill, ...changes } : skill)),
    );
  return (
    <div className="space-y-5" data-testid="skill-definitions-editor">
      <p className="text-sm text-muted-foreground">{t("skills.editorHelp")}</p>
      {value.map((skill, index) => (
        <section className="space-y-5 rounded-xl bg-muted/40 p-5" key={index}>
          <div className="flex items-center justify-between">
            <h3 className="font-semibold">
              {skill.name || t("skills.newSkill")}
            </h3>
            <Button
              variant="ghost"
              size="sm"
              disabled={disabled}
              onClick={() => onChange(value.filter((_, i) => i !== index))}
            >
              {t("skills.remove")}
            </Button>
          </div>
          <label className="block space-y-2 text-sm">
            <span>{t("skills.name")}</span>
            <Input
              value={skill.name}
              aria-label={t("skills.name")}
              maxLength={64}
              disabled={disabled}
              placeholder="verify-sources"
              onChange={(event) => update(index, { name: event.target.value })}
            />
            <span className="block text-xs text-muted-foreground">
              {t("skills.nameHelp")}
            </span>
          </label>
          <label className="block space-y-2 text-sm">
            <span>{t("skills.description")}</span>
            <Textarea
              rows={3}
              value={skill.description}
              maxLength={1024}
              disabled={disabled}
              onChange={(event) =>
                update(index, { description: event.target.value })
              }
            />
          </label>
          <label className="block space-y-2 text-sm">
            <span>{t("skills.instructions")}</span>
            <Textarea
              rows={9}
              value={skill.instructions}
              maxLength={50000}
              disabled={disabled}
              onChange={(event) =>
                update(index, { instructions: event.target.value })
              }
            />
          </label>
          <h4 className="text-sm font-medium">{t("skills.tools")}</h4>
          <CapabilityPackPicker
            kind="tool-pack"
            projectId={projectId}
            value={skill.tool_packs}
            disabled={disabled}
            onOpen={onOpen}
            onChange={(refs) =>
              update(index, { tool_packs: refs as ToolPackReference[] })
            }
          />
        </section>
      ))}
      {!!value.length && !validSkills(value) && (
        <p role="alert" className="text-sm text-destructive">
          {t("skills.validation")}
        </p>
      )}
      <Button
        variant="outline"
        disabled={disabled || value.length >= 50}
        onClick={() =>
          onChange([
            ...value,
            { name: "", description: "", instructions: "", tool_packs: [] },
          ])
        }
      >
        {t("skills.add")}
      </Button>
    </div>
  );
}
