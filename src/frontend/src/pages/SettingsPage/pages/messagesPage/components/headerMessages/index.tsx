import { useTranslation } from "react-i18next";
import SettingsPageHeader from "@/pages/SettingsPage/components/SettingsPageHeader";

const HeaderMessagesComponent = () => {
  const { t } = useTranslation();
  return (
    <SettingsPageHeader
      title={t("messages.title")}
      description={t("messages.description")}
    />
  );
};
export default HeaderMessagesComponent;
