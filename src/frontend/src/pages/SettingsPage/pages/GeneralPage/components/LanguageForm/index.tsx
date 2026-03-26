import { useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useTypesStore } from "@/stores/typesStore";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "../../../../../../components/ui/card";

const LANGUAGES = [
  { code: "en", label: "English" },
  { code: "fr", label: "Français" },
  { code: "es", label: "Español" },
  { code: "de", label: "Deutsch" },
  { code: "pt", label: "Português" },
  { code: "ja", label: "日本語" },
  { code: "zh-Hans", label: "中文" },
];

const LanguageFormComponent = () => {
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
    <Card>
      <CardHeader>
        <CardTitle>{t("settings.languageTitle")}</CardTitle>
        <CardDescription>{t("settings.languageDescription")}</CardDescription>
      </CardHeader>
      <CardContent>
        <select
          value={i18n.language}
          onChange={(e) => handleChange(e.target.value)}
          className="rounded border border-border bg-background px-2 py-1.5 text-sm text-foreground"
        >
          {LANGUAGES.map((lang) => (
            <option key={lang.code} value={lang.code}>
              {lang.label}
              {lang.code === "en"
                ? ` (${t("settings.languageRecommended")})`
                : ""}
            </option>
          ))}
        </select>
      </CardContent>
    </Card>
  );
};

export default LanguageFormComponent;
