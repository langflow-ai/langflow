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
            className="text-destructive h-4 w-4"
          />
        ),
      },
      {
        condition: conditionInactive,
        icon: (
          <ForwardedIconComponent
            name="CircleOff"
            className="text-muted-foreground h-4 w-4"
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
