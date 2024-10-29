import { BuildStatus } from "../../constants/enums";
import { VertexBuildTypeAPI } from "../../types/api";

export const getSpecificClassFromBuildStatus = (
  buildStatus: BuildStatus | undefined,
  validationStatus: VertexBuildTypeAPI | null,
  isBuilding: boolean,
): string => {
  let isInvalid = validationStatus && !validationStatus.valid;

  if (isInvalid || buildStatus === BuildStatus.ERROR) {
    return "border-destructive border-[1.5px]";
  } else {
    return "";
  }
};
