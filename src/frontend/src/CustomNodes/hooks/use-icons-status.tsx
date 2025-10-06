import ForwardedIconComponent from "../../components/common/genericIconComponent";
import { BuildStatus } from "../../constants/enums";

const useIconStatus = (buildStatus: BuildStatus | undefined) => {
  const conditionError = buildStatus === BuildStatus.ERROR;
  const conditionInactive = buildStatus === BuildStatus.INACTIVE;

  const renderIconStatus = () => {
    if (buildStatus === BuildStatus.BUILDING) {
      return <></>;
    }

    const iconConditions = [
      {
        condition: conditionError,
        icon: (
          <ForwardedIconComponent
            name="CircleAlert"
            className="h-4 w-4 text-destructive"
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
