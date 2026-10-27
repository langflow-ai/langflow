import { useCallback, useState } from "react";
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
  /** Only token-only providers may renew a manually entered credential. */
  reauthorizing: boolean;
  initialAllowBackgroundRuns?: boolean;
  /** Stores the validated token through creation or renewal. */
  create: (payload: ConnectionCreate) => Promise<ConnectionRead>;
  tokenProfile?: ManualTokenProfileRead;
  tokenOnly: boolean;
}

export interface SlackTokenConnection {
  offersToken: boolean;
  /** The token method is offered and chosen. */
  usesToken: boolean;
  method: ConnectionMethod;
  setMethod: (method: ConnectionMethod) => void;
  token: string;
  setToken: (token: string) => void;
  requiresExpiry: boolean;
  expiresAt: string;
  setExpiresAt: (expiresAt: string) => void;
  expiresAtValid: boolean;
  tokenKind: SlackTokenKind | null;
  allowBackgroundRuns: boolean;
  setAllowBackgroundRuns: (allow: boolean) => void;
  /** Validate and store the pasted token without a consent window. */
  createWithToken: (details: {
    name: string;
    displayName: string;
  }) => Promise<ConnectionRead>;
  /** Forget the pasted token and restore the provider's default method. */
  reset: () => void;
}

function isExactFutureLocalTime(value: string): boolean {
  const match =
    /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2})(?:\.(\d{1,3}))?)?$/.exec(
      value,
    );
  if (!match) return false;
  const parsed = new Date(value);
  return (
    parsed.getTime() > Date.now() &&
    parsed.getFullYear() === Number(match[1]) &&
    parsed.getMonth() + 1 === Number(match[2]) &&
    parsed.getDate() === Number(match[3]) &&
    parsed.getHours() === Number(match[4]) &&
    parsed.getMinutes() === Number(match[5]) &&
    parsed.getSeconds() === Number(match[6] ?? 0) &&
    parsed.getMilliseconds() === Number((match[7] ?? "").padEnd(3, "0"))
  );
}

/** Token entry shared by Slack and installed providers with a validator. */
export function useSlackTokenConnection({
  providerId,
  deploymentContext,
  reauthorizing,
  initialAllowBackgroundRuns = false,
  create,
  tokenProfile,
  tokenOnly,
}: UseSlackTokenConnectionOptions): SlackTokenConnection {
  const [selectedMethod, setMethod] = useState<ConnectionMethod | null>(null);
  const [token, setToken] = useState("");
  const [expiresAt, setExpiresAt] = useState("");
  // Renewal retains the owner's consent. New connections require explicit consent.
  const [allowBackgroundRuns, setAllowBackgroundRuns] = useState(
    initialAllowBackgroundRuns,
  );

  const offersToken =
    (!reauthorizing || tokenOnly) &&
    (offersSlackToken(providerId, deploymentContext) ||
      tokenProfile !== undefined);
  const defaultMethod =
    offersToken && providerId !== "slack" && tokenProfile ? "token" : "oauth";
  const method = !offersToken
    ? "oauth"
    : tokenOnly
      ? "token"
      : (selectedMethod ?? defaultMethod);
  const usesToken = offersToken && method === "token";
  const tokenKind = slackTokenKind(token);
  const requiresExpiry = tokenProfile?.requires_expiry === true;
  const expiresAtValid = !requiresExpiry || isExactFutureLocalTime(expiresAt);

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
        credentials: {
          access_token: token.trim(),
          ...(requiresExpiry
            ? { expires_at: new Date(expiresAt).toISOString() }
            : {}),
        },
      }),
    [
      create,
      providerId,
      allowBackgroundRuns,
      token,
      tokenProfile,
      requiresExpiry,
      expiresAt,
    ],
  );

  const reset = useCallback(() => {
    setMethod(null);
    setToken("");
    setExpiresAt("");
    setAllowBackgroundRuns(initialAllowBackgroundRuns);
  }, [initialAllowBackgroundRuns]);

  return {
    offersToken,
    usesToken,
    method,
    setMethod,
    token,
    setToken,
    requiresExpiry,
    expiresAt,
    setExpiresAt,
    expiresAtValid,
    tokenKind,
    allowBackgroundRuns,
    setAllowBackgroundRuns,
    createWithToken,
    reset,
  };
}
