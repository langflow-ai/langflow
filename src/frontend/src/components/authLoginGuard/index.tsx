import { useContext } from "react";
import { Navigate } from "react-router-dom";
import { AuthContext } from "../../contexts/authContext";
import { LOCALHOST_JWT } from "../../constants/constants";

export const ProtectedLoginRoute = ({ children }) => {
  const { getAuthentication } = useContext(AuthContext);

  const isLocalHost = window.location.href.includes("localhost");

  if(isLocalHost && LOCALHOST_JWT){
    window.location.replace("/");
    return <Navigate to="/" replace />;
  }

  if (getAuthentication()) {
    window.location.replace("/");
    return <Navigate to="/" replace />;
  }

  return children;
};
