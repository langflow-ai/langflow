import { LANGFLOW_AUTO_LOGIN_OPTION } from "@/constants/constants";
import useAuthStore from "@/stores/authStore";

export const ProtectedRoute = ({ children }) => {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const hasToken = !!localStorage.getItem(LANGFLOW_AUTO_LOGIN_OPTION);
  const isLoginPage = location.pathname.includes("login");
  const logout = useAuthStore((state) => state.logout);

  if (!isAuthenticated && hasToken && !isLoginPage) {
    logout();
  } else {
    return children;
  }
};
