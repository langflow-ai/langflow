import { useTranslation } from "react-i18next";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { type SlackTokenKind, slackTokenKind } from "../helpers/slack-token";
import type { ConnectionMethod } from "../hooks/useSlackTokenConnection";
import ScopeChecklist from "./ScopeChecklist";

export interface SlackTokenFieldsProps {
  token: string;
  onTokenChange: (token: string) => void;
  allowBackgroundRuns: boolean;
  onAllowBackgroundRunsChange: (allow: boolean) => void;
  /** The scopes a bot token can be recorded with, offered once one is pasted. */
  botTokenScopes: string[];
  tokenScopes: Set<string>;
  onToggleTokenScope: (scope: string, checked: boolean) => void;
}

export interface ConnectionMethodSelectProps {
  method: ConnectionMethod;
  onMethodChange: (method: ConnectionMethod) => void;
}

/** Sign in through the provider, or paste a token. */
export function ConnectionMethodSelect({
  method,
  onMethodChange,
}: ConnectionMethodSelectProps) {
  const { t } = useTranslation();
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor="connection-method">{t("connections.add.method")}</Label>
      <select
        id="connection-method"
        className="h-9 rounded-md border border-border bg-background px-2 text-sm"
        value={method}
        onChange={(event) =>
          onMethodChange(event.target.value as ConnectionMethod)
        }
        data-testid="connection-method"
      >
        <option value="oauth">{t("connections.add.methodOauth")}</option>
        <option value="token">{t("connections.add.methodToken")}</option>
      </select>
    </div>
  );
}

const HINT_KEY: Record<SlackTokenKind, string> = {
  app: "connections.add.tokenApp",
  bot: "connections.add.tokenBot",
};

/** The token, scope and background-runs fields of a pasted-token Slack connection. */
export function SlackTokenFields({
  token,
  onTokenChange,
  allowBackgroundRuns,
  onAllowBackgroundRunsChange,
  botTokenScopes,
  tokenScopes,
  onToggleTokenScope,
}: SlackTokenFieldsProps) {
  const { t } = useTranslation();
  const kind = slackTokenKind(token);
  const invalid = token.trim().length > 0 && kind === null;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="connection-token">{t("connections.add.token")}</Label>
        <Input
          id="connection-token"
          type="password"
          autoComplete="off"
          spellCheck={false}
          value={token}
          onChange={(event) => onTokenChange(event.target.value)}
          aria-invalid={invalid}
          aria-describedby="connection-token-help"
          className="aria-[invalid=true]:border-destructive aria-[invalid=true]:ring-1 aria-[invalid=true]:ring-destructive"
          data-testid="connection-token"
        />
        <p
          id="connection-token-help"
          className={
            invalid
              ? "text-xs text-destructive"
              : "text-xs text-muted-foreground"
          }
          data-testid="connection-token-help"
        >
          {invalid
            ? t("connections.add.tokenInvalid")
            : t(kind ? HINT_KEY[kind] : "connections.add.tokenHelp")}
        </p>
      </div>

      <div className="flex flex-col gap-1">
        <label className="flex items-center gap-2 text-sm">
          <Checkbox
            checked={allowBackgroundRuns}
            onCheckedChange={(checked) =>
              onAllowBackgroundRunsChange(checked === true)
            }
            aria-describedby="connection-allow-background-runs-help"
            data-testid="connection-allow-background-runs"
          />
          {t("connections.add.allowBackgroundRuns")}
        </label>
        <p
          id="connection-allow-background-runs-help"
          className="pl-6 text-xs text-muted-foreground"
        >
          {t("connections.add.allowBackgroundRunsHelp")}
        </p>
      </div>

      {kind === "bot" && (
        <div className="flex flex-col gap-2">
          <span className="text-sm font-medium">
            {t("connections.add.tokenScopes")}
          </span>
          <ScopeChecklist
            scopes={botTokenScopes}
            selected={tokenScopes}
            onToggle={onToggleTokenScope}
          />
        </div>
      )}
    </div>
  );
}

export default SlackTokenFields;
