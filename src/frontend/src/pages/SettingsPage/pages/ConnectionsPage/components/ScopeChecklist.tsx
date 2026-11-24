import { useTranslation } from "react-i18next";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { normalizeScope } from "@/utils/connection-scopes";
import { type ScopeRequirement, shortScope } from "../helpers/scopes";

export interface ScopeChecklistProps {
  providerId: string;
  requirements: ScopeRequirement[];
  scopes: string[];
  selected: Set<string>;
  onToggle: (scope: string, checked: boolean) => void;
  /** Scopes the connection already holds, marked so a cleared one stays recognizable. */
  granted?: Set<string>;
}

/** One checkbox per scope an authorization request may ask for. */
export function ScopeChecklist({
  providerId,
  requirements,
  scopes,
  selected,
  onToggle,
  granted,
}: ScopeChecklistProps) {
  const { t } = useTranslation();
  return (
    <div className="flex flex-col gap-3">
      {scopes.map((scope) => {
        const matches = (value: string) =>
          normalizeScope(providerId, value) ===
          normalizeScope(providerId, scope);
        const actions = requirements.filter(
          (requirement) =>
            requirement.requiredScopes.some(matches) ||
            requirement.conditionalScopes.some((entry) => matches(entry.scope)),
        );
        return (
          <label key={scope} className="flex items-start gap-2 text-xs">
            <Checkbox
              className="mt-0.5"
              checked={selected.has(scope)}
              onCheckedChange={(checked) => onToggle(scope, Boolean(checked))}
              data-testid={`connection-scope-${scope}`}
            />
            <span className="flex min-w-0 flex-1 flex-col gap-1">
              {actions.map((action) => (
                <span
                  key={action.capabilityId}
                  className="flex flex-wrap items-center gap-2"
                >
                  <span className="font-medium">{action.displayName}</span>
                  <Badge
                    variant={
                      action.risk === "read" ? "secondaryStatic" : "outline"
                    }
                    size="tag"
                  >
                    {t(`connections.scope.risk.${action.risk}`, {
                      defaultValue: action.risk,
                    })}
                  </Badge>
                  {!action.requiredScopes.some(matches) && (
                    <span className="text-muted-foreground">
                      {t("connections.scope.conditional")}
                    </span>
                  )}
                </span>
              ))}
              <span
                className="break-all font-mono text-muted-foreground"
                title={scope}
              >
                {shortScope(scope)}
              </span>
            </span>
            {granted?.has(scope) && (
              <Badge variant="secondaryStatic" size="xq">
                {t("connections.add.granted")}
              </Badge>
            )}
          </label>
        );
      })}
    </div>
  );
}

export default ScopeChecklist;
