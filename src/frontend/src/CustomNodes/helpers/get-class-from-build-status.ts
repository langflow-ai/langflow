import { BuildStatus } from "../../constants/enums";
import { VertexBuildTypeAPI } from "../../types/api";

export const getSpecificClassFromBuildStatus = (
  buildStatus: BuildStatus | undefined,
  validationStatus: VertexBuildTypeAPI | null,
  isDark: boolean,
): string => {
  let isInvalid = validationStatus && !validationStatus.valid;
  if (isInvalid || buildStatus === BuildStatus.ERROR) {
    return "border-destructive";
  } else if (buildStatus === BuildStatus.BUILDING) {
    return "building-status";
  } else if (buildStatus === BuildStatus.BUILT) {
    return "border-emerald-success";
  } else {
    return "";
  }
};
