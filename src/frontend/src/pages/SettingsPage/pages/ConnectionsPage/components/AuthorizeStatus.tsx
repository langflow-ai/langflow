import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Badge } from "@/components/ui/badge";
import type { ConnectionRead } from "@/controllers/API/queries/connections";
import { shortScope } from "../helpers/scopes";

export type AuthorizeState =
  | { kind: "waiting" }
  | { kind: "connected"; connection: ConnectionRead }
  | { kind: "failed"; message: string };

export interface AuthorizeStatusProps {
  state: AuthorizeState | null;
}

/** Where a new or re-authorized connection's consent stands. */
export function AuthorizeStatus({ state }: AuthorizeStatusProps) {
  const { t } = useTranslation();

  if (state?.kind === "waiting") {
    return (
      <div className="flex items-center gap-3 text-sm">
        <ForwardedIconComponent
          name="Loader2"
          className="h-4 w-4 animate-spin"
        />
        {t("connections.add.waiting")}
      </div>
    );
  }
  if (state?.kind === "connected") {
    return (
      <div className="flex flex-col gap-2 text-sm">
        <span className="flex items-center gap-2 font-medium">
          <ForwardedIconComponent
            name="CircleCheckBig"
            className="h-4 w-4 text-accent-emerald-foreground"
          />
          {t("connections.add.connected")}
        </span>
        <div className="flex flex-wrap gap-1">
          {state.connection.granted_scopes.map((scope) => (
            <Badge key={scope} variant="secondaryStatic" size="xq">
              {shortScope(scope)}
            </Badge>
          ))}
        </div>
      </div>
    );
  }
  if (state?.kind === "failed") {
    return (
      <p className="text-sm text-destructive" role="alert">
        {state.message}
      </p>
    );
  }
  return null;
}

export default AuthorizeStatus;
