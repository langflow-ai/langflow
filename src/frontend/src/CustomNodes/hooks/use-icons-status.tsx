import ForwardedIconComponent from "../../components/genericIconComponent";
import Checkmark from "../../components/ui/checkmark";
import Loading from "../../components/ui/loading";
import Xmark from "../../components/ui/xmark";
import { BuildStatus } from "../../constants/enums";
import { VertexBuildTypeAPI } from "../../types/api";

const useIconStatus = (
  buildStatus: BuildStatus | undefined,
  validationStatus: VertexBuildTypeAPI | null,
) => {
  const conditionSuccess =
    !(!buildStatus || buildStatus === BuildStatus.TO_BUILD) &&
    validationStatus &&
    validationStatus.valid;
  const conditionError = buildStatus === BuildStatus.ERROR;
  const conditionInactive = buildStatus === BuildStatus.INACTIVE;

  const renderIconStatus = () => {
    if (buildStatus === BuildStatus.BUILDING) {
      return <Loading className="mr-1 text-medium-indigo" size={20} />;
    } else {
      return (
        <>
          {conditionSuccess ? (
            <Checkmark
              className="h-6 w-6 stroke-2 text-status-green transition-all"
              isVisible={true}
            />
          ) : conditionError ? (
            <Xmark
              isVisible={true}
              className="h-6 w-6 fill-current stroke-2 text-status-red"
            />
          ) : conditionInactive ? (
            <ForwardedIconComponent
              name="CircleOff"
              className="h-5 w-5 text-muted-foreground"
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
