import { useTranslation } from "react-i18next";
import type { BadgeProps } from "@/components/ui/badge";
import { Badge } from "@/components/ui/badge";

// Values produced by `_tool_access_hint` in lfx/base/mcp/util.py from the MCP
// server's ToolAnnotations. A tool whose source declares nothing has no hint.
const HINT_STYLES: Record<
  string,
  { variant: BadgeProps["variant"]; labelKey: string }
> = {
  read_only: {
    variant: "secondaryStatic",
    labelKey: "toolsModal.accessReadOnly",
  },
  write: { variant: "outline", labelKey: "toolsModal.accessWrite" },
  destructive: {
    variant: "errorStatic",
    labelKey: "toolsModal.accessDestructive",
  },
};

export function AccessHintBadge({
  hint,
}: {
  hint?: string | null;
}): JSX.Element | null {
  const { t } = useTranslation();
  const style = hint ? HINT_STYLES[hint] : undefined;

  // No badge rather than an "unknown" one: most servers send no annotations, and a
  // column of placeholders would read as a finding about the tool.
  if (!style) return null;

  return (
    <Badge
      variant={style.variant}
      size="sm"
      className="cursor-default"
      title={t("toolsModal.accessHintTooltip")}
      data-testid={`access-hint-${hint}`}
    >
      {t(style.labelKey)}
    </Badge>
  );
}
