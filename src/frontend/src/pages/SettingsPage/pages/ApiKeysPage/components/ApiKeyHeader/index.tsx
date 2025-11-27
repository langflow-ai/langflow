import ForwardedIconComponent from "../../../../../../components/common/genericIconComponent";
import { Button } from "../../../../../../components/ui/button";
import { API_PAGE_PARAGRAPH } from "../../../../../../constants/constants";
import SecretKeyModal from "../../../../../../modals/secretKeyModal";
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
  const modalProps = getModalPropsApiKey();
  return (
    <>
      <div className="flex w-full items-center justify-between gap-4">
        <div className="flex flex-col w-full">
          <h2 className="text-primary-font flex gap-2 items-center text-lg font-medium">
            Ai Studio API Keys
            <ForwardedIconComponent name="Key" className="h-4 w-4 text-menu" />
          </h2>
          <p className="text-sm text-secondary-font">{API_PAGE_PARAGRAPH}</p>
        </div>
        <div className="flex items-center gap-2">
          <SecretKeyModal
            modalProps={modalProps}
            data={userId}
            onCloseModal={fetchApiKeys}
          >
            <Button data-testid="api-key-button-store" variant="default">
              <ForwardedIconComponent name="Plus" className="w-4" />
              Add New
            </Button>
          </SecretKeyModal>
        </div>
      </div>
    </>
  );
};
export default ApiKeyHeaderComponent;
