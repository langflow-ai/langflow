import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "../../../../../../components/common/genericIconComponent";
import { Button } from "../../../../../../components/ui/button";
import SecretKeyModal from "../../../../../../modals/secretKeyModal";
import SettingsPageHeader from "../../../../components/SettingsPageHeader";
import { getModalPropsApiKey } from "../../helpers/get-modal-props";

type ApiKeyHeaderComponentProps = {
  selectedRows: string[];
  fetchApiKeys: () => void;
  userId: string;
};
const ApiKeyHeaderComponent = ({
  selectedRows,
  fetchApiKeys,
  userId,
}: ApiKeyHeaderComponentProps) => {
  const { t } = useTranslation();
  const modalProps = getModalPropsApiKey(t);
  return (
    <>
      <SettingsPageHeader
        title={t("settings.apiKeysTitle")}
        description={t("settings.apiPageParagraph")}
      >
        <SecretKeyModal
          modalProps={modalProps}
          data={userId}
          onCloseModal={fetchApiKeys}
        >
          <Button data-testid="api-key-button-store" size="sm">
            <ForwardedIconComponent name="Plus" className="w-4" />
            {t("settings.addNewKey")}
          </Button>
        </SecretKeyModal>
      </SettingsPageHeader>
    </>
  );
};
export default ApiKeyHeaderComponent;
