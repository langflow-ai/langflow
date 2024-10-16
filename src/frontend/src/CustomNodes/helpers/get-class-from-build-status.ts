import { BuildStatus } from "../../constants/enums";
import { VertexBuildTypeAPI } from "../../types/api";

export const getSpecificClassFromBuildStatus = (
  buildStatus: BuildStatus | undefined,
  validationStatus: VertexBuildTypeAPI | null,
  isDark: boolean,
  selected: boolean,
): string => {
  let isInvalid = validationStatus && !validationStatus.valid;
  if ((isInvalid || buildStatus === BuildStatus.ERROR) && !selected) {
    return isDark ? "built-invalid-status-dark" : "built-invalid-status";
  } else if (buildStatus === BuildStatus.BUILDING) {
    return "building-status";
  } else if (buildStatus === BuildStatus.BUILT && !selected) {
    return "border-emerald-success";
  } else {
    return "";
  }
};
