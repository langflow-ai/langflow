import type { OAuthRegistrationRead } from "@/controllers/API/queries/connections";

export interface RegistrationChoice {
  provider: string;
  /** The identity the connection will execute as, which selects the profile. */
  identity: "user_delegated" | "bot" | "service";
  /** What `GET /connections/oauth/registrations` returned, or null on an older backend. */
  registrations: OAuthRegistrationRead[] | null;
  /** The id the user picked, when the operator configured more than one. */
  preferredId?: string | null;
}

/**
 * Seam for choosing the registration an authorization request names.
 *
 * Registration ids are operator-chosen (`google-work`), so OSS picks among what
 * the backend lists: the caller's choice when it is still on offer, otherwise
 * the first registration for this provider and identity. A distribution that
 * provisions registrations itself replaces this file to resolve them its own way
 * (a hosted deployment with one registration per provider, say).
 *
 * Returning null means "no registration can serve this", and the dialog says so
 * instead of starting a consent the backend would refuse.
 */
export function resolveRegistrationId({
  provider,
  identity,
  registrations,
  preferredId,
}: RegistrationChoice): string | null {
  if (registrations === null) {
    // The backend predates the listing route; the provider id is the only
    // guess available, and it matches an instance named after its provider.
    return provider;
  }
  const profile = identity === "bot" ? "bot" : "user";
  const candidates = registrations.filter(
    (registration) =>
      registration.provider === provider && registration.profile === profile,
  );
  if (candidates.length === 0) return null;
  if (preferredId && candidates.some(({ id }) => id === preferredId)) {
    return preferredId;
  }
  return candidates[0].id;
}

/**
 * Seam for showing the provider's consent screen.
 *
 * OSS opens a popup on the browser the user is already in, because the OAuth
 * callback binds a cookie to that browser. A desktop build replaces this file to
 * hand the URL to the system browser instead.
 */
export function openAuthorizationUrl(
  url: string,
  popup: Window | null,
): Window | null {
  if (popup && !popup.closed) {
    popup.location.href = url;
    popup.focus();
    return popup;
  }
  return window.open(url, "langflow-oauth-consent", "width=520,height=700");
}
