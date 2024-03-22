import BaseModal from "../../modals/baseModal";
import { fetchErrorComponentType } from "../../types/components";
import IconComponent from "../genericIconComponent";
import { Button } from "../ui/button";

export default function FetchErrorComponent({
  message,
  description,
  openModal,
  setRetry,
  isLoadingHealth,
}: fetchErrorComponentType) {
  return (
    <>
      <BaseModal size="small-h-full" open={openModal} type="modal">
        <BaseModal.Content>
          <div role="status" className="m-auto flex flex-col items-center">
            <IconComponent
              className={`h-16 w-16`}
              name="Unplug"
            ></IconComponent>
            <br></br>
            <span className="text-lg text-almost-medium-blue">{message}</span>
            <span className="text-lg text-almost-medium-blue">
              {description}
            </span>
          </div>
        </BaseModal.Content>

        <BaseModal.Footer>
          <div className="m-auto">
            <Button
              disabled={isLoadingHealth}
              onClick={() => {
                setRetry();
              }}
            >
              {isLoadingHealth ? (
                <div>
                  <IconComponent name={"Loader2"} className={"animate-spin"} />
                </div>
              ) : (
                "Retry"
              )}
            </Button>
          </div>
        </BaseModal.Footer>
      </BaseModal>
    </>
  );
}
