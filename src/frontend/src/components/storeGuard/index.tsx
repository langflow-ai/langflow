import { Navigate } from "react-router-dom";
import { useStoreStore } from "../../stores/storeStore";

export const StoreGuard = ({ children }) => {
  const hasStore = useStoreStore((state) => state.hasStore);

  if (!hasStore) {
    return <Navigate to="/all" replace />;
  }

  return children;
};
