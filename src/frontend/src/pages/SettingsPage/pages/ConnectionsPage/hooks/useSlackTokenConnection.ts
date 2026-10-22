import { useCallback, useEffect, useState } from "react";
import type {
  ConnectionCreate,
  ConnectionRead,
  DeploymentContext,
  ManualTokenProfileRead,
} from "@/controllers/API/queries/connections";
import {
  offersSlackToken,
  type SlackTokenKind,
  slackTokenKind,
} from "../helpers/slack-token";

/** Sign in through the provider, or use a provider-validated token. */
export type ConnectionMethod = "oauth" | "token";

export interface UseSlackTokenConnectionOptions {
  providerId: string;
  /** Which deployment this is; hosted offers no pasted tokens. */
  deploymentContext: DeploymentContext | undefined;
  /** Re-authorizing an existing connection never offers a token. */
  reauthorizing: boolean;
  /** Creates the connection row (`POST /connections`). */
  create: (payload: ConnectionCreate) => Promise<ConnectionRead>;
  tokenProfile?: ManualTokenProfileRead;
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

/** Token entry shared by Slack and installed providers with a validator. */
export function useSlackTokenConnection({
  providerId,
  deploymentContext,
  reauthorizing,
  create,
  tokenProfile,
}: UseSlackTokenConnectionOptions): SlackTokenConnection {
  const [method, setMethod] = useState<ConnectionMethod>("oauth");
  const [token, setToken] = useState("");
  // Consent to unattended use is explicit and off by default: pasting a token
  // is not the same as allowing a trigger to run with it.
  const [allowBackgroundRuns, setAllowBackgroundRuns] = useState(false);

  const offersToken =
    !reauthorizing &&
    (offersSlackToken(providerId, deploymentContext) ||
      tokenProfile !== undefined);
  const usesToken = offersToken && method === "token";
  const tokenKind = slackTokenKind(token);
  useEffect(() => {
    if (providerId !== "slack" && tokenProfile) setMethod("token");
  }, [providerId, tokenProfile]);

  const createWithToken = useCallback(
    ({ name, displayName }: { name: string; displayName: string }) =>
      create({
        provider_key: providerId,
        name,
        display_name: displayName,
        ownership_mode: "user",
        executing_identity: { identity: tokenProfile?.identity ?? "bot" },
        // The server validates the token and replaces untrusted grant claims.
        granted_scopes: tokenProfile?.required_scopes ?? [],
        allow_non_interactive: allowBackgroundRuns,
        credentials: { access_token: token.trim() },
      }),
    [create, providerId, allowBackgroundRuns, token, tokenProfile],
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
