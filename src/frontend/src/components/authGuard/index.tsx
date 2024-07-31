import { LANGFLOW_AUTO_LOGIN_OPTION } from "@/constants/constants";
import useAuthStore from "@/stores/authStore";
import { useContext } from "react";
import { AuthContext } from "../../contexts/authContext";

export const ProtectedRoute = ({ children }) => {
  const { logout } = useContext(AuthContext);
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const hasToken = !!localStorage.getItem(LANGFLOW_AUTO_LOGIN_OPTION);

  if (!isAuthenticated && hasToken) {
    logout();
  } else {
    return children;
  }
};
