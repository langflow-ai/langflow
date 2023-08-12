import { useContext } from "react";
import { Navigate } from "react-router-dom";
import { AuthContext } from "../../contexts/authContext";

export const ProtectedRoute = ({ children }) => {
  const { isAuthenticated, logout, getAuthentication } =
    useContext(AuthContext);
  if (!isAuthenticated && !getAuthentication()) {
    logout();
    return <Navigate to="/login" replace />;
  }

  return children;
};
