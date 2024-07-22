import useAuthStore from "@/stores/authStore";
import { useContext } from "react";
import { AuthContext } from "../../contexts/authContext";

export const ProtectedRoute = ({ children }) => {
  const { logout } = useContext(AuthContext);
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);

  if (!isAuthenticated) {
    logout();
  } else {
    return children;
  }
};
