import useFlowStore from "@/stores/flowStore";
import { BuildStatus } from "../../constants/enums";
import { VertexBuildTypeAPI } from "../../types/api";

export const getSpecificClassFromBuildStatus = (
  buildStatus: BuildStatus | undefined,
  validationStatus: VertexBuildTypeAPI | null,
  isBuilding: boolean,
): string => {
  let isInvalid = validationStatus && !validationStatus.valid;
  if (isInvalid || buildStatus === BuildStatus.ERROR) {
    return "border-destructive";
  } else if (buildStatus === BuildStatus.BUILDING) {
    return "building-status";
  } else if (buildStatus === BuildStatus.BUILT && isBuilding) {
    return "border-emerald-success";
  } else {
    return "";
  }
};
