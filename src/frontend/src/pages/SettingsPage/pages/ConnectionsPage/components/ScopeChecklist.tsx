import { useTranslation } from "react-i18next";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { shortScope } from "../helpers/scopes";

export interface ScopeChecklistProps {
  scopes: string[];
  selected: Set<string>;
  onToggle: (scope: string, checked: boolean) => void;
  /** Scopes the connection already holds, marked so a cleared one stays recognizable. */
  granted?: Set<string>;
}

/** One checkbox per scope an authorization request may ask for. */
export function ScopeChecklist({
  scopes,
  selected,
  onToggle,
  granted,
}: ScopeChecklistProps) {
  const { t } = useTranslation();
  return (
    <div className="flex flex-col gap-1.5">
      {scopes.map((scope) => (
        <label
          key={scope}
          className="flex items-center gap-2 font-mono text-xs"
        >
          <Checkbox
            checked={selected.has(scope)}
            onCheckedChange={(checked) => onToggle(scope, Boolean(checked))}
            data-testid={`connection-scope-${scope}`}
          />
          {shortScope(scope)}
          {granted?.has(scope) && (
            <Badge variant="secondaryStatic" size="xq">
              {t("connections.add.granted")}
            </Badge>
          )}
        </label>
      ))}
    </div>
  );
}

export default ScopeChecklist;
