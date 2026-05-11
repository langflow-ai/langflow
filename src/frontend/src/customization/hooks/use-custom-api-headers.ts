import { useTranslation } from "react-i18next";

export function useCustomApiHeaders() {
  const { i18n } = useTranslation();
  return {
    "Accept-Language": i18n.language || "en",
  };
}
