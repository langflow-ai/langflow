import { Link, LinkProps, useParams } from "react-router-dom";
import { ENABLE_CUSTOM_PARAM } from "../feature-flags";

export function CustomLink({ to, ...props }: LinkProps) {
  const { customParam } = useParams();

  const newLocation =
    ENABLE_CUSTOM_PARAM && to[0] === "/" ? `/${customParam}${to}` : to;

  return <Link to={newLocation} {...props} />;
}
