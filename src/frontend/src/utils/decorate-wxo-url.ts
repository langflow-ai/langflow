const UTM_MEDIUM = "integration";
const UTM_CAMPAIGN = "wxo-integration";
const DEFAULT_UTM_SOURCE = "langflow";

function getUtmSource(): string {
  const configured = import.meta.env.LANGFLOW_WXO_UTM_SOURCE;
  return typeof configured === "string" && configured.length > 0
    ? configured
    : DEFAULT_UTM_SOURCE;
}

function isIbmHost(hostname: string): boolean {
  return hostname === "ibm.com" || hostname.endsWith(".ibm.com");
}

export function decorateWxoUrl(url: string, utmContent?: string): string {
  let parsed: URL;
  try {
    parsed = new URL(url);
  } catch {
    return url;
  }

  if (!isIbmHost(parsed.hostname)) {
    return url;
  }

  parsed.searchParams.set("utm_source", getUtmSource());
  parsed.searchParams.set("utm_medium", UTM_MEDIUM);
  parsed.searchParams.set("utm_campaign", UTM_CAMPAIGN);
  if (utmContent) {
    parsed.searchParams.set("utm_content", utmContent);
  }

  return parsed.toString();
}
