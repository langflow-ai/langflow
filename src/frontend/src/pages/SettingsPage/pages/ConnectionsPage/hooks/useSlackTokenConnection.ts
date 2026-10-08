import { useCallback, useEffect, useMemo, useState } from "react";
import type {
  ConnectionCreate,
  ConnectionRead,
  DeploymentContext,
  IntegrationProviderRead,
} from "@/controllers/API/queries/connections";
import { useTypesStore } from "@/stores/typesStore";
import { scopeRequirements, uniqueScopes } from "../helpers/scopes";
import {
  offersSlackToken,
  type SlackTokenKind,
  slackTokenKind,
} from "../helpers/slack-token";

/** Sign in through the provider, or paste a token (Slack only). */
export type ConnectionMethod = "oauth" | "token";

/** The auth profile a Slack bot token stands in for. */
const SLACK_BOT_PROFILE = "slack-bot-install";

export interface UseSlackTokenConnectionOptions {
  providerId: string;
  provider: IntegrationProviderRead | undefined;
  /** Which deployment this is; hosted offers no pasted tokens. */
  deploymentContext: DeploymentContext | undefined;
  /** Re-authorizing an existing connection never offers a token. */
  reauthorizing: boolean;
  /** Creates the connection row (`POST /connections`). */
  create: (payload: ConnectionCreate) => Promise<ConnectionRead>;
}

export interface SlackTokenConnection {
  offersToken: boolean;
  /** The token method is offered and chosen. */
  usesToken: boolean;
  method: ConnectionMethod;
  setMethod: (method: ConnectionMethod) => void;
  token: string;
  setToken: (token: string) => void;
  tokenKind: SlackTokenKind | null;
  /** The scopes a pasted bot token can be recorded with: the "as app" actions'. */
  botTokenScopes: string[];
  tokenScopes: Set<string>;
  toggleTokenScope: (scope: string, checked: boolean) => void;
  allowBackgroundRuns: boolean;
  setAllowBackgroundRuns: (allow: boolean) => void;
  /** Store the pasted token as a connection: no consent window, nothing to wait for. */
  createWithToken: (details: {
    name: string;
    displayName: string;
  }) => Promise<ConnectionRead>;
  /** Forget the pasted token and go back to signing in. */
  reset: () => void;
}

/** The "paste a token" method of the add-connection dialog, for Slack. */
export function useSlackTokenConnection({
  providerId,
  provider,
  deploymentContext,
  reauthorizing,
  create,
}: UseSlackTokenConnectionOptions): SlackTokenConnection {
  const typesData = useTypesStore((state) => state.data);
  const [method, setMethod] = useState<ConnectionMethod>("oauth");
  const [token, setToken] = useState("");
  const [tokenScopes, setTokenScopes] = useState<Set<string>>(new Set());
  // Consent to unattended use is explicit and off by default: pasting a token
  // is not the same as allowing a trigger to run with it.
  const [allowBackgroundRuns, setAllowBackgroundRuns] = useState(false);

  const offersToken =
    !reauthorizing && offersSlackToken(providerId, deploymentContext);
  const usesToken = offersToken && method === "token";
  const tokenKind = slackTokenKind(token);

  // What a pasted bot token is for: the actions that run as the app's bot.
  const botTokenScopes = useMemo(
    () =>
      uniqueScopes(
        scopeRequirements(
          (provider?.capabilities ?? []).filter(
            (capability) => capability.auth_profile_id === SLACK_BOT_PROFILE,
          ),
          typesData,
        ),
      ),
    [provider, typesData],
  );

  // Keyed on the scope list's content, not its identity: the types store hands
  // back a new object on every refetch (window focus included - which is
  // exactly when someone returns from copying a token), and resetting on that
  // would silently re-check a scope the person had just unchecked.
  const botTokenScopeKey = botTokenScopes.join(" ");
  useEffect(() => {
    setTokenScopes(
      new Set(botTokenScopeKey ? botTokenScopeKey.split(" ") : []),
    );
  }, [botTokenScopeKey]);

  const toggleTokenScope = useCallback(
    (scope: string, checked: boolean) =>
      setTokenScopes((current) => {
        const next = new Set(current);
        if (checked) next.add(scope);
        else next.delete(scope);
        return next;
      }),
    [],
  );

  const createWithToken = useCallback(
    ({ name, displayName }: { name: string; displayName: string }) =>
      create({
        provider_key: providerId,
        name,
        display_name: displayName,
        ownership_mode: "user",
        executing_identity: { identity: "bot" },
        // An app-level token's scope is recorded by the server, never claimed.
        granted_scopes: tokenKind === "bot" ? [...tokenScopes] : [],
        allow_non_interactive: allowBackgroundRuns,
        credentials: { access_token: token.trim() },
      }),
    [create, providerId, tokenKind, tokenScopes, allowBackgroundRuns, token],
  );

  const reset = useCallback(() => {
    setMethod("oauth");
    setToken("");
    setAllowBackgroundRuns(false);
  }, []);

  return {
    offersToken,
    usesToken,
    method,
    setMethod,
    token,
    setToken,
    tokenKind,
    botTokenScopes,
    tokenScopes,
    toggleTokenScope,
    allowBackgroundRuns,
    setAllowBackgroundRuns,
    createWithToken,
    reset,
  };
}
