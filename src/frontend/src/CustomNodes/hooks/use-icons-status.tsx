import IconComponent from "../../components/genericIconComponent";
import Checkmark from "../../components/ui/checkmark";
import Loading from "../../components/ui/loading";
import Xmark from "../../components/ui/xmark";
import { BuildStatus } from "../../constants/enums";
import { VertexBuildTypeAPI } from "../../types/api";

const useIconStatus = (
  buildStatus: BuildStatus | undefined,
  validationStatus: VertexBuildTypeAPI | null
) => {
  const renderIconStatus = () => {
    if (buildStatus === BuildStatus.BUILDING) {
      return <Loading className="text-medium-indigo" />;
    } else {
      return (
        <>
          <IconComponent
            name="Play"
            className="absolute ml-0.5 h-5 fill-current stroke-2 text-medium-indigo opacity-0 transition-all group-hover:opacity-100"
          />
          {validationStatus && validationStatus.valid ? (
            <Checkmark
              className="absolute ml-0.5 h-5 stroke-2 text-status-green opacity-100 transition-all group-hover:opacity-0"
              isVisible={true}
            />
          ) : validationStatus &&
            !validationStatus.valid &&
            buildStatus === BuildStatus.INACTIVE ? (
            <IconComponent
              name="Play"
              className="absolute ml-0.5 h-5 fill-current stroke-2 text-status-green opacity-30 transition-all group-hover:opacity-0"
            />
          ) : buildStatus === BuildStatus.ERROR ||
            (validationStatus && !validationStatus.valid) ? (
            <Xmark
              isVisible={true}
              className="absolute ml-0.5 h-5 fill-current stroke-2 text-status-red opacity-100 transition-all group-hover:opacity-0"
            />
          ) : (
            <IconComponent
              name="Play"
              className="absolute ml-0.5 h-5 fill-current stroke-2 text-muted-foreground opacity-100 transition-all group-hover:opacity-0"
            />
          )}
        </>
      );
    }
  };

  return renderIconStatus();
};

export default useIconStatus;
