/**
 * Slack tokens a person can paste in, and what each one is for.
 *
 * Only Slack connections can be made from a pasted token, and only these two
 * kinds: an app-level token (`xapp-`) opens Socket Mode sockets for Slack
 * triggers, and a bot token (`xoxb-`) lets the "as app" actions call Slack -
 * on Desktop, where there is no bot sign-in, pasting it is the only way. The
 * server decides what the token may do; this only tells the person what they
 * pasted.
 */
import type { DeploymentContext } from "@/controllers/API/queries/connections/types";

export type SlackTokenKind = "app" | "bot";

export const SLACK_PROVIDER_ID = "slack";

export function slackTokenKind(token: string): SlackTokenKind | null {
  const value = token.trim();
  if (value.startsWith("xapp-")) return "app";
  if (value.startsWith("xoxb-")) return "bot";
  return null;
}

/**
 * Whether the "paste a token" method is offered. Hosted serves every tenant
 * from one Slack Marketplace app, which signs people in through OAuth and
 * cannot use Socket Mode, so hosted never offers it - and neither does a
 * deployment that has not said what it is yet. The server refuses an
 * app-level token on hosted either way; this only keeps the option out of
 * sight where it cannot work.
 */
export function offersSlackToken(
  providerId: string,
  deploymentContext: DeploymentContext | undefined,
): boolean {
  return (
    providerId === SLACK_PROVIDER_ID &&
    deploymentContext !== undefined &&
    deploymentContext !== "hosted"
  );
}
