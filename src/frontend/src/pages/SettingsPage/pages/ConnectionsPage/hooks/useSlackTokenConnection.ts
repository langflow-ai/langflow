import { useCallback, useState } from "react";
import type {
  ConnectionCreate,
  ConnectionRead,
  DeploymentContext,
} from "@/controllers/API/queries/connections";
import {
  offersSlackToken,
  type SlackTokenKind,
  slackTokenKind,
} from "../helpers/slack-token";

/** Sign in through the provider, or paste a token (Slack only). */
export type ConnectionMethod = "oauth" | "token";

export interface UseSlackTokenConnectionOptions {
  providerId: string;
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
  allowBackgroundRuns: boolean;
  setAllowBackgroundRuns: (allow: boolean) => void;
  /** Validate and store the pasted token without a consent window. */
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
  deploymentContext,
  reauthorizing,
  create,
}: UseSlackTokenConnectionOptions): SlackTokenConnection {
  const [method, setMethod] = useState<ConnectionMethod>("oauth");
  const [token, setToken] = useState("");
  // Consent to unattended use is explicit and off by default: pasting a token
  // is not the same as allowing a trigger to run with it.
  const [allowBackgroundRuns, setAllowBackgroundRuns] = useState(false);

  const offersToken =
    !reauthorizing && offersSlackToken(providerId, deploymentContext);
  const usesToken = offersToken && method === "token";
  const tokenKind = slackTokenKind(token);

  const createWithToken = useCallback(
    ({ name, displayName }: { name: string; displayName: string }) =>
      create({
        provider_key: providerId,
        name,
        display_name: displayName,
        ownership_mode: "user",
        executing_identity: { identity: "bot" },
        // The server records scopes from Slack, never from a client claim.
        granted_scopes: [],
        allow_non_interactive: allowBackgroundRuns,
        credentials: { access_token: token.trim() },
      }),
    [create, providerId, allowBackgroundRuns, token],
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
    allowBackgroundRuns,
    setAllowBackgroundRuns,
    createWithToken,
    reset,
  };
}
