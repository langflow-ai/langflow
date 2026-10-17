import { useTranslation } from "react-i18next";
import SettingsPageHeader from "@/pages/SettingsPage/components/SettingsPageHeader";

const GeneralPageHeaderComponent = () => {
  const { t } = useTranslation();
  return (
    <SettingsPageHeader
      title={t("settings.generalTitle")}
      description={t("settings.generalDescription")}
    />
  );
};
export default GeneralPageHeaderComponent;
