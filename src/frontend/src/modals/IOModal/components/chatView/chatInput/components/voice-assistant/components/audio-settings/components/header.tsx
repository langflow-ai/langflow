import { useTranslation } from "react-i18next";
import IconComponent from "../../../../../../../../../../components/common/genericIconComponent";
import { ICON_STROKE_WIDTH } from "../../../../../../../../../../constants/constants";

const AudioSettingsHeader = () => {
  const { t } = useTranslation();
  return (
    <div
      className="grid gap-1 p-4"
      data-testid="voice-assistant-settings-modal-header"
    >
      <p className="flex items-center gap-2 text-sm text-primary">
        <IconComponent
          name="Settings"
          strokeWidth={ICON_STROKE_WIDTH}
          className="h-4 w-4 text-muted-foreground hover:text-foreground"
        />
        {t("voice.settingsTitle")}
      </p>
      <p className="text-mmd leading-4 text-muted-foreground">
        {t("voice.settingsDescription")}
      </p>
    </div>
  );
};

export default AudioSettingsHeader;
