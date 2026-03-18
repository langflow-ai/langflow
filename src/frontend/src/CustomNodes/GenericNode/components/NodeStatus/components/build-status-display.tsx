import { useTranslation } from "react-i18next";
import { BuildStatus } from "@/constants/enums";

const StatusMessage = ({ children, className = "text-foreground" }) => (
  <span className={`flex ${className}`}>{children}</span>
);

const TimeStamp = ({ prefix, time }) => (
  <div className="flex items-center text-sm text-secondary-foreground">
    <div>{prefix}</div>
    <div className="ml-1 text-secondary-foreground">{time}</div>
  </div>
);

const Duration = ({ duration }) => (
  <div className="flex items-center text-secondary-foreground">
    <div>Duration:</div>
    <div className="ml-1">{duration}</div>
  </div>
);

const ValidationDetails = ({
  validationString,
  lastRunTime,
  validationStatus,
}) => {
  const { t } = useTranslation();
  return (
    <div className="max-h-100 px-1 py-2.5">
      <div className="flex max-h-80 flex-col gap-2">
        {validationString && (
          <div className="break-words text-sm text-foreground">
            {validationString}
          </div>
        )}
        {lastRunTime && (
          <TimeStamp prefix={t("flow.runTimestampPrefix")} time={lastRunTime} />
        )}
        <Duration duration={validationStatus?.data.duration} />
      </div>
    </div>
  );
};

const BuildStatusDisplay = ({
  buildStatus,
  validationStatus,
  validationString,
  lastRunTime,
}) => {
  const { t } = useTranslation();

  if (buildStatus === BuildStatus.BUILDING) {
    return <StatusMessage>{t("flow.statusBuilding")}</StatusMessage>;
  }

  if (buildStatus === BuildStatus.INACTIVE) {
    return <StatusMessage>{t("flow.statusInactive")}</StatusMessage>;
  }

  if (buildStatus === BuildStatus.ERROR && !validationStatus) {
    // If the build status is error and there is no validation status, it means that it failed before building, so show the Missing Required Fields error message
    return <StatusMessage>{t("flow.statusMissingFieldsError")}</StatusMessage>;
  }

  if (!validationStatus) {
    return <StatusMessage>{t("flow.statusBuild")}</StatusMessage>;
  }

  return (
    <ValidationDetails
      validationString={validationString}
      lastRunTime={lastRunTime}
      validationStatus={validationStatus}
    />
  );
};

export default BuildStatusDisplay;
