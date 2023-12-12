import { useContext } from "react";
import { Navigate } from "react-router-dom";
import { StoreContext } from "../../contexts/storeContext";

export const StoreGuard = ({ children }) => {
  const { hasStore } = useContext(StoreContext);
  if (!hasStore) {
    return <Navigate to="/flows" replace />;
  }

  return children;
};
