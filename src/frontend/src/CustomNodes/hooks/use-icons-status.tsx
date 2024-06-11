import ForwardedIconComponent from "../../components/genericIconComponent";
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
          {conditionSuccess ? (
            <Checkmark
              className="h-6 w-6 stroke-2 text-status-green transition-all"
              isVisible={true}
            />
          ) : conditionInactive ? (
            <ForwardedIconComponent
              name="Ellipsis"
              className="h-6 w-6 fill-current stroke-2 text-status-gray opacity-30"
            />
          ) : conditionError ? (
            <Xmark
              isVisible={true}
              className="h-6 w-6 fill-current stroke-2 text-status-red"
            />
          ) : (
            <ForwardedIconComponent
              name="Ellipsis"
              className="h-6 w-6 fill-current stroke-2 text-status-gray opacity-70"
            />
          )}
        </>
      );
    }
  };

  return renderIconStatus();
};

export default useIconStatus;
