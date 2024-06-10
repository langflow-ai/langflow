import IconComponent from "../../components/genericIconComponent";
import Checkmark from "../../components/ui/checkmark";
import Loading from "../../components/ui/loading";
import Xmark from "../../components/ui/xmark";
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
        <>
          <IconComponent
            name="Play"
            className={cn(
              !conditionSuccess && !conditionInactive && !conditionError
                ? "opacity-100"
                : "opacity-0",
              "absolute ml-0.5 h-5 fill-current stroke-2 text-muted-foreground transition-all group-hover:text-medium-indigo group-hover/node:opacity-100",
            )}
          />
          {conditionSuccess ? (
            <Checkmark
              className="absolute ml-0.5 h-5 stroke-2 text-status-green opacity-100 transition-all group-hover/node:opacity-0"
              isVisible={true}
            />
          ) : conditionInactive ? (
            <IconComponent
              name="Play"
              className="absolute ml-0.5 h-5 fill-current stroke-2 text-status-gray opacity-30 transition-all group-hover/node:opacity-0"
            />
          ) : conditionError ? (
            <Xmark
              isVisible={true}
              className="absolute ml-0.5 h-5 fill-current stroke-2 text-status-red opacity-100 transition-all group-hover/node:opacity-0"
            />
          ) : (
            <></>
          )}
        </>
      );
    }
  };

  return renderIconStatus();
};

export default useIconStatus;
