const PROVIDER_ALIASES: Record<string, string> = {
  "IBM watsonx.ai": "IBM WatsonX",
};

export const canonicalProviderName = (providerName: string): string =>
  PROVIDER_ALIASES[providerName] ?? providerName;

export const providerNamesMatch = (left: string, right: string): boolean =>
  canonicalProviderName(left) === canonicalProviderName(right);
