import { useContext } from "react";
import { Navigate } from "react-router-dom";
import { AuthContext } from "../../contexts/authContext";

export const ProtectedRoute = ({ children }) => {
  const { isAuthenticated, logout} =
    useContext(AuthContext);
  if (!isAuthenticated) {
    logout();
    return <Navigate to="/login" replace />;
  }

  return children;
};
