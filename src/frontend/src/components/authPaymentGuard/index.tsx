import {useContext} from "react";
import {Navigate} from "react-router-dom";
import {AuthContext} from "../../contexts/authContext";

export const ProtectedPaymentRoute = ({ children }) => {
  const { userData } =
    useContext(AuthContext);

  if (userData!.stripe_subscription_status != "active") {
    return <Navigate to="/payment" />;
  }

  return children;
};