import { useContext } from "react";
import { AuthContext } from "../../contexts/authContext";

export const ProtectedRoute = ({ children }) => {
  const { isAuthenticated, logout } = useContext(AuthContext);
  if (!isAuthenticated) {
    logout();
  } else {
    return children;
  }
};
