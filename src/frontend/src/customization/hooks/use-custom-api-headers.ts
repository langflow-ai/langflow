import i18n from "@/i18n";

export function useCustomApiHeaders() {
  return {
    "Accept-Language": i18n.language || "en",
  };
}
