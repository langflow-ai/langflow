import { useTranslation } from "react-i18next";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { type SlackTokenKind, slackTokenKind } from "../helpers/slack-token";

export interface SlackTokenFieldsProps {
  token: string;
  onTokenChange: (token: string) => void;
  allowBackgroundRuns: boolean;
  onAllowBackgroundRunsChange: (allow: boolean) => void;
}

const HINT_KEY: Record<SlackTokenKind, string> = {
  app: "connections.add.tokenApp",
  bot: "connections.add.tokenBot",
};

/** The token and background-runs fields of a pasted-token Slack connection. */
export function SlackTokenFields({
  token,
  onTokenChange,
  allowBackgroundRuns,
  onAllowBackgroundRunsChange,
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
    </div>
  );
}

export default SlackTokenFields;
