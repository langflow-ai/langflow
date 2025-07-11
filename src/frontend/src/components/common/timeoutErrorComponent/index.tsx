import BaseModal from "../../../modals/baseModal";
import { fetchErrorComponentType } from "../../../types/components";
import Loading from "../../ui/loading";

export default function TimeoutErrorComponent({
  message,
  description,
  openModal,
  setRetry,
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
            <Loading className={`h-16 w-16`} />
            <br></br>
            <span className="text-primary text-lg">{message}</span>
            <span className="text-primary text-center text-lg">
              {description}
            </span>
          </div>
        </BaseModal.Content>

        <BaseModal.Footer />
      </BaseModal>
    </>
  );
}
