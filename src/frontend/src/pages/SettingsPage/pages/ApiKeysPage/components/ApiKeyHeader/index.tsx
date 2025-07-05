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
      <div className="flex w-full items-start justify-between gap-6">
        <div className="flex w-full flex-col">
          <h2 className="flex items-center text-lg font-semibold tracking-tight">
            Langflow API Keys
            <ForwardedIconComponent
              name="Key"
              className="ml-2 h-5 w-5 text-primary"
            />
          </h2>
          <p className="text-sm text-muted-foreground">{API_PAGE_PARAGRAPH}</p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <SecretKeyModal
            modalProps={modalProps}
            data={userId}
            onCloseModal={fetchApiKeys}
          >
            <Button data-testid="api-key-button-store" variant="primary">
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
