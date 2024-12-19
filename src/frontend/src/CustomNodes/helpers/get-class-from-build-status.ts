import { BuildStatus } from "../../constants/enums";
import { VertexBuildTypeAPI } from "../../types/api";

export const getSpecificClassFromBuildStatus = (
  buildStatus: BuildStatus | undefined,
  validationStatus: VertexBuildTypeAPI | null,
  isBuilding: boolean,
): string => {
  let isInvalid = validationStatus && !validationStatus.valid;

  if (BuildStatus.BUILDING === buildStatus) {
    return "border-foreground border-[1px] ring-[0.75px] ring-foreground";
  } else if ((isInvalid || buildStatus === BuildStatus.ERROR) && !isBuilding) {
    return "border-destructive border-[1px] ring-[0.75px] ring-destructive";
  } else {
    return "";
  }
};
