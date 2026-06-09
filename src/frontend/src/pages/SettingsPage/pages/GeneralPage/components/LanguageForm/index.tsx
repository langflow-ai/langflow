import { useTranslation } from "react-i18next";
import LanguageSelector from "@/components/core/appHeaderComponent/components/LanguageSelector";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "../../../../../../components/ui/card";

/**
 * 渲染常规设置页面中的语言设置卡片。
 * Renders the language settings card on the General settings page.
 *
 * @returns 设置页语言选择器卡片。 / The settings language selector card.
 */
const LanguageFormComponent = () => {
  const { t } = useTranslation();

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("settings.languageTitle")}</CardTitle>
        <CardDescription>{t("settings.languageDescription")}</CardDescription>
      </CardHeader>
      <CardContent>
        <LanguageSelector triggerClassName="w-full" />
      </CardContent>
    </Card>
  );
};

export default LanguageFormComponent;
