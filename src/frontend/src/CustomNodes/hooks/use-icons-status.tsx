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
    buildStatus === BuildStatus.BUILT ||
    (!(!buildStatus || buildStatus === BuildStatus.TO_BUILD) &&
      validationStatus &&
      validationStatus.valid);
  const conditionError = buildStatus === BuildStatus.ERROR;
  const conditionInactive = buildStatus === BuildStatus.INACTIVE;
  const renderIconStatus = () => {
    if (buildStatus === BuildStatus.BUILDING) {
      return (
        <Loading
          data-testid="loading_icon"
          className="mr-1 text-medium-indigo"
          size={20}
        />
      );
    }

    const iconConditions = [
      {
        condition: conditionSuccess,
        icon: (
          <Checkmark
            className="text-emerald-success h-4 w-4 stroke-2 transition-all"
            isVisible={true}
          />
        ),
      },
      {
        condition: conditionError,
        icon: (
          <Xmark
            isVisible={true}
            className="h-4 w-4 fill-current stroke-2 text-destructive"
          />
        ),
      },
      {
        condition: conditionInactive,
        icon: (
          <ForwardedIconComponent
            name="CircleOff"
            className="h-4 w-4 text-muted-foreground"
          />
        ),
      },
    ];

    const activeIcon = iconConditions.find(({ condition }) => condition)?.icon;
    return activeIcon || null;
  };

  return renderIconStatus();
};

export default useIconStatus;
