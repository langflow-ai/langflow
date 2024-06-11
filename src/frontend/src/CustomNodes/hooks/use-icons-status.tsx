import Loading from "../../components/ui/loading";
import { BuildStatus } from "../../constants/enums";
import { VertexBuildTypeAPI } from "../../types/api";
import { cn } from "../../utils/utils";

const useIconStatus = (
  buildStatus: BuildStatus | undefined,
  validationStatus: VertexBuildTypeAPI | null,
) => {
  const conditionSuccess = validationStatus && validationStatus.valid;
  const conditionInactive =
    validationStatus &&
    !validationStatus.valid &&
    buildStatus === BuildStatus.INACTIVE;
  const conditionError =
    buildStatus === BuildStatus.ERROR ||
    (validationStatus && !validationStatus.valid);

  const renderIconStatus = () => {
    if (buildStatus === BuildStatus.BUILDING) {
      return <Loading className="text-medium-indigo" />;
    } else {
      return (
        <div
          className={cn(
            "h-4 w-4 shrink-0 rounded-full",
            conditionSuccess
              ? "bg-status-green"
              : conditionInactive
                ? "bg-status-gray"
                : conditionError
                  ? "bg-status-red"
                  : "bg-muted-foreground/40",
          )}
        />
      );
    }
  };

  return renderIconStatus();
};

export default useIconStatus;
