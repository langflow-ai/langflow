import { useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { SUPPORTED_LANGUAGES } from "@/constants/languages";
import { useTypesStore } from "@/stores/typesStore";

export const LanguageSelector = () => {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const setTypes = useTypesStore((state) => state.setTypes);

  const handleChange = (code: string) => {
    i18n.changeLanguage(code);
    localStorage.setItem("languagePreference", code);
    setTypes({});
    queryClient.invalidateQueries({ queryKey: ["useGetTypes"] });
  };

  return (
    <select
      aria-label={t("settings.languageSelectAriaLabel")}
      value={i18n.language}
      onChange={(e) => handleChange(e.target.value)}
      className="rounded border border-border bg-background px-1 py-0.5 text-sm text-foreground"
    >
      {SUPPORTED_LANGUAGES.map((lang) => (
        <option key={lang.code} value={lang.code}>
          {lang.label}
        </option>
      ))}
    </select>
  );
};

export default LanguageSelector;
