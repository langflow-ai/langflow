import { BASENAME } from "@/customization/config-constants";

const SETUP_GUIDES = new Map([
  [
    "google",
    "https://docs.langflow.org/connection-oauth#customer-owned-google-registration",
  ],
  ["microsoft", "https://docs.langflow.org/entra-app-registration"],
  [
    "slack",
    "https://docs.langflow.org/connection-oauth#customer-owned-slack-registration",
  ],
]);

export function connectionSetupGuide(
  provider: string,
  usesToken = false,
  docsUrl?: string | null,
) {
  if (provider === "slack" && usesToken) {
    return "https://docs.langflow.org/bundles-slack#two-executing-identities";
  }
  const guide = SETUP_GUIDES.get(provider);
  if (guide) return guide;
  if (!docsUrl) return undefined;
  try {
    const url = new URL(docsUrl);
    if (
      (url.protocol === "https:" || url.protocol === "http:") &&
      !url.username &&
      !url.password
    ) {
      return url.href;
    }
  } catch {
    return undefined;
  }
  return undefined;
}

export function suggestedCallbackUrl(provider: string, origin: string) {
  if (!SETUP_GUIDES.has(provider)) return undefined;
  try {
    const url = new URL(origin);
    const loopback = ["localhost", "127.0.0.1", "[::1]"].includes(url.hostname);
    // Match the broker's HTTPS / loopback HTTP rule. Desktop shells may have
    // a non-HTTP origin, which cannot be registered as an OAuth callback.
    if (url.protocol !== "https:" && !(url.protocol === "http:" && loopback)) {
      return undefined;
    }
    return `${url.origin}${BASENAME}/api/v1/connections/oauth/${provider}/callback`;
  } catch {
    return undefined;
  }
}
