import {
  type NavigateFunction,
  type NavigateOptions,
  type To,
  useNavigate,
  useParams,
} from "react-router-dom";
import { ENABLE_CUSTOM_PARAM } from "../feature-flags";

export function useCustomNavigate(): NavigateFunction {
  const domNavigate = useNavigate();

  const { customParam } = useParams();

  function navigate(to: To | number, options?: NavigateOptions) {
    if (typeof to === "number") {
      domNavigate(to);
    } else {
      domNavigate(
        ENABLE_CUSTOM_PARAM && to[0] === "/" ? `/${customParam}${to}` : to,
        options,
      );
    }
  }

  return navigate;
}
