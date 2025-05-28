import { CustomNavigate } from "@/customization/components/custom-navigate";
import { useStoreStore } from "../../../stores/storeStore";

export const StoreGuard = ({ children }) => {
  const hasStore = useStoreStore((state) => state.hasStore);

  if (!hasStore) {
    return <CustomNavigate to="/all" replace />;
  }

  return children;
};
