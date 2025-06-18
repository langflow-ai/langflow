import FetchErrorComponent from "@/components/common/fetchErrorComponent";
import { fetchErrorComponentType } from "@/types/components";

export function CustomFetchErrorComponent({
  message,
  description,
  openModal,
  setRetry,
  isLoadingHealth,
}: fetchErrorComponentType) {
  return (
    <FetchErrorComponent
      message={message}
      description={description}
      openModal={openModal}
      setRetry={setRetry}
      isLoadingHealth={isLoadingHealth}
    />
  );
}

export default CustomFetchErrorComponent;
