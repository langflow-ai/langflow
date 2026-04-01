import { useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { loadLanguage } from "@/i18n";
import { SUPPORTED_LANGUAGES } from "@/constants/languages";
import { useTypesStore } from "@/stores/typesStore";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "../../../../../../components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const LanguageFormComponent = () => {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const setTypes = useTypesStore((state) => state.setTypes);

  const handleChange = async (code: string) => {
    await loadLanguage(code);
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
        <Select value={i18n.language} onValueChange={handleChange}>
          <SelectTrigger aria-label={t("settings.languageSelectAriaLabel")}>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {SUPPORTED_LANGUAGES.map((lang) => (
              <SelectItem key={lang.code} value={lang.code}>
                {lang.label}
                {lang.code === "en"
                  ? ` (${t("settings.languageRecommended")})`
                  : ""}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </CardContent>
    </Card>
  );
};

export default LanguageFormComponent;
