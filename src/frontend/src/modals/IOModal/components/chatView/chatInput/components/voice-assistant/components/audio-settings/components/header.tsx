import React from "react";
import IconComponent from "../../../../../../../../../../components/common/genericIconComponent";
import { ICON_STROKE_WIDTH } from "../../../../../../../../../../constants/constants";

const AudioSettingsHeader = () => {
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
        Voice settings
      </p>
      <p className="text-mmd leading-4 text-muted-foreground">
        Voice chat is powered by OpenAI. You can also add more voices with
        ElevenLabs.
      </p>
    </div>
  );
};

export default AudioSettingsHeader;
