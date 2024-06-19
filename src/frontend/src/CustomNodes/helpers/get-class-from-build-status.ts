import { BuildStatus } from "../../constants/enums";
import { VertexBuildTypeAPI } from "../../types/api";

export const getSpecificClassFromBuildStatus = (
  buildStatus: BuildStatus | undefined,
  validationStatus: VertexBuildTypeAPI | null,
  isDark: boolean,
) => {
  let isInvalid = validationStatus && !validationStatus.valid;
  if (
    (buildStatus === BuildStatus.BUILT && isInvalid) ||
    buildStatus === BuildStatus.ERROR
  ) {
    return isDark ? "built-invalid-status-dark" : "built-invalid-status";
  } else if (buildStatus === BuildStatus.BUILDING) {
    return "building-status";
  } else {
    return "";
  }
};
