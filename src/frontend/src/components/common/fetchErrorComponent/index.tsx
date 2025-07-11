import BaseModal from "../../../modals/baseModal";
import { fetchErrorComponentType } from "../../../types/components";
import IconComponent from "../genericIconComponent";

export default function FetchErrorComponent({
  message,
  description,
  openModal,
  setRetry,
  isLoadingHealth,
}: fetchErrorComponentType) {
  return (
    <>
      <BaseModal
        size="small-h-full"
        open={openModal}
        type="modal"
        onSubmit={() => {
          setRetry();
        }}
      >
        <BaseModal.Content>
          <div role="status" className="m-auto flex flex-col items-center">
            <IconComponent
              className={`h-16 w-16`}
              name="Unplug"
            ></IconComponent>
            <br></br>
            <span className="text-primary text-lg">{message}</span>
            <span className="text-primary text-lg">{description}</span>
          </div>
        </BaseModal.Content>

        <BaseModal.Footer
          submit={{
            label: "Retry",
            loading: isLoadingHealth,
            onClick: () => {
              setRetry();
            },
          }}
        />
      </BaseModal>
    </>
  );
}
