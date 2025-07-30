import { Navigate, type NavigateProps, useParams } from "react-router-dom";
import { ENABLE_CUSTOM_PARAM } from "../feature-flags";

export function CustomNavigate({ to, ...props }: NavigateProps) {
  const { customParam } = useParams();
  const newLocation =
    ENABLE_CUSTOM_PARAM && to[0] === "/" ? `/${customParam}${to}` : to;

  return <Navigate to={newLocation} {...props} />;
}
