import { useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { SUPPORTED_LANGUAGES } from "@/constants/languages";
import { useTypesStore } from "@/stores/typesStore";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "../../../../../../components/ui/card";

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
          aria-label={t("settings.languageSelectAriaLabel")}
          value={i18n.language}
          onChange={(e) => handleChange(e.target.value)}
          className="rounded border border-border bg-background px-2 py-1.5 text-sm text-foreground"
        >
          {SUPPORTED_LANGUAGES.map((lang) => (
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
