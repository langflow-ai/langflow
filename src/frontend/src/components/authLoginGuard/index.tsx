import { useContext } from "react";
import { Navigate } from "react-router-dom";
import { AuthContext } from "../../contexts/authContext";

export const ProtectedLoginRoute = ({ children }) => {
  const { getAuthentication } = useContext(AuthContext);

  if (getAuthentication()) {
    window.location.replace('/');
    return <Navigate to="/" replace />;
  }

  return children;
};
