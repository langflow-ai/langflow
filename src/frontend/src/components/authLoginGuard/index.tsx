import { useContext } from "react";
import { Navigate } from "react-router-dom";
import { AuthContext } from "../../contexts/authContext";

export const ProtectedLoginRoute = ({ children }) => {
  const { getAuthentication, autoLogin } = useContext(AuthContext);

  if (autoLogin === true) {
    window.location.replace("/");
    return <Navigate to="/" replace />;
  }

  if (getAuthentication()) {
    window.location.replace("/");
    return <Navigate to="/" replace />;
  }

  return children;
};
