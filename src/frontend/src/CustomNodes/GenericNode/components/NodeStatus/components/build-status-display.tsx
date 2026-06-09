import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import {
  STATUS_BUILD,
  STATUS_BUILDING,
  STATUS_INACTIVE,
  STATUS_MISSING_FIELDS_ERROR,
} from "@/constants/constants";
import { BuildStatus } from "@/constants/enums";
import type { UsageType } from "@/types/chat";
import { formatTokenCount } from "@/utils/format-token-count";

const StatusMessage = ({ children, className = "text-foreground" }) => (
  <span className={`flex ${className}`}>{children}</span>
);

const TimeStamp = ({ prefix, time }) => (
  <div className="flex items-center text-xxs text-secondary-foreground">
    <div>{prefix}</div>
    <div className="ml-1 text-secondary-foreground">{time}</div>
  </div>
);

const Duration = ({ duration }) => (
  <div className="flex items-center text-xxs text-secondary-foreground">
    <div>Duration:</div>
    <div className="ml-auto">{duration}</div>
  </div>
);

const TokenUsageDisplay = ({ tokenUsage }: { tokenUsage: UsageType }) => (
  <div className="flex flex-col gap-1 text-secondary-foreground">
    <div className="flex items-center">
      <div className="text-xxs">Input tokens:</div>
      <div className="ml-auto flex items-center gap-1 font-mono text-xs">
        <ForwardedIconComponent
          name="Coins"
          className="h-3 w-3 text-secondary-foreground"
        />
        {formatTokenCount(tokenUsage.input_tokens)}
      </div>
    </div>
    <div className="flex items-center">
      <div className="text-xxs">Output tokens:</div>
      <div className="ml-auto flex items-center gap-1 font-mono text-xs">
        <ForwardedIconComponent
          name="Coins"
          className="h-3 w-3 text-secondary-foreground text-xs"
        />
        {formatTokenCount(tokenUsage.output_tokens)}
      </div>
    </div>
  </div>
);

const ValidationDetails = ({
  validationString,
  lastRunTime,
  validationStatus,
}) => {
  const { t } = useTranslation();
  return (
    <div className="flex max-h-100 flex-col gap-1">
      {validationString && (
        <div className="break-words text-sm text-foreground">
          {validationString}
        </div>
      )}
      {lastRunTime && (
        <TimeStamp prefix={t("flow.runTimestampPrefix")} time={lastRunTime} />
      )}
      <Duration duration={validationStatus?.data.duration} />
      {validationStatus?.data?.token_usage && (
        <TokenUsageDisplay tokenUsage={validationStatus.data.token_usage} />
      )}
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
