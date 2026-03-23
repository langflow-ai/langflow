import { useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useTypesStore } from "@/stores/typesStore";

const LANGUAGES = [
  { code: "en", label: "English" },
  { code: "fr", label: "Français" },
  { code: "es", label: "Español" },
  { code: "de", label: "Deutsch" },
  { code: "pt", label: "Português" },
  { code: "ja", label: "日本語" },
  { code: "zh-Hans", label: "中文" },
];

export const LanguageSelector = () => {
  const { i18n } = useTranslation();
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
      value={i18n.language}
      onChange={(e) => handleChange(e.target.value)}
      className="rounded border border-border bg-background px-1 py-0.5 text-sm text-foreground"
    >
      {LANGUAGES.map((lang) => (
        <option key={lang.code} value={lang.code}>
          {lang.label}
        </option>
      ))}
    </select>
  );
};

export default LanguageSelector;
