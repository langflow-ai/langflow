import {
  RUN_TIMESTAMP_PREFIX,
  STATUS_BUILD,
  STATUS_BUILDING,
  STATUS_INACTIVE,
  STATUS_MISSING_FIELDS_ERROR,
} from "@/constants/constants";
import { BuildStatus } from "@/constants/enums";

const StatusMessage = ({ children, className = "text-foreground" }) => (
  <span className={`flex ${className}`}>{children}</span>
);

const TimeStamp = ({ prefix, time }) => (
  <div className="text-secondary-foreground flex items-center text-sm">
    <div>{prefix}</div>
    <div className="text-secondary-foreground ml-1">{time}</div>
  </div>
);

const Duration = ({ duration }) => (
  <div className="text-secondary-foreground flex items-center">
    <div>Duration:</div>
    <div className="ml-1">{duration}</div>
  </div>
);

const ValidationDetails = ({
  validationString,
  lastRunTime,
  validationStatus,
}) => (
  <div className="max-h-100 px-1 py-2.5">
    <div className="flex max-h-80 flex-col gap-2">
      {validationString && (
        <div className="text-foreground text-sm break-words">
          {validationString}
        </div>
      )}
      {lastRunTime && (
        <TimeStamp prefix={RUN_TIMESTAMP_PREFIX} time={lastRunTime} />
      )}
      <Duration duration={validationStatus?.data.duration} />
    </div>
  </div>
);

const BuildStatusDisplay = ({
  buildStatus,
  validationStatus,
  validationString,
  lastRunTime,
}) => {
  if (buildStatus === BuildStatus.BUILDING) {
    return <StatusMessage>{STATUS_BUILDING}</StatusMessage>;
  }

  if (buildStatus === BuildStatus.INACTIVE) {
    return <StatusMessage>{STATUS_INACTIVE}</StatusMessage>;
  }

  if (buildStatus === BuildStatus.ERROR && !validationStatus) {
    // If the build status is error and there is no validation status, it means that it failed before building, so show the Missing Required Fields error message
    return <StatusMessage>{STATUS_MISSING_FIELDS_ERROR}</StatusMessage>;
  }

  if (!validationStatus) {
    return <StatusMessage>{STATUS_BUILD}</StatusMessage>;
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
