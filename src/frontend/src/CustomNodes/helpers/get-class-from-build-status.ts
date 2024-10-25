import { BuildStatus } from "../../constants/enums";
import { VertexBuildTypeAPI } from "../../types/api";

export const getSpecificClassFromBuildStatus = (
  buildStatus: BuildStatus | undefined,
  validationStatus: VertexBuildTypeAPI | null,
  isBuilding: boolean,
  currentNodeId: string,
): string => {
  let isInvalid = validationStatus && !validationStatus.valid;
  const currentNodeBuilding = currentNodeId === validationStatus?.id;

  if (isInvalid || buildStatus === BuildStatus.ERROR) {
    return "border-destructive border-[1.5px]";
  } else if (buildStatus === BuildStatus.BUILT && isBuilding) {
    return "border-emerald-success border-[1.5px]";
  } else {
    return "";
  }
};
