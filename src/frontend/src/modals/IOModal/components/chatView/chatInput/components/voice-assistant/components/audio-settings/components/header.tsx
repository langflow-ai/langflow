import React from "react";
import IconComponent from "../../../../../../../../../../components/common/genericIconComponent";
import { ICON_STROKE_WIDTH } from "../../../../../../../../../../constants/constants";

const AudioSettingsHeader = () => {
  return (
    <div
      className="grid gap-1 p-4"
      data-testid="voice-assistant-settings-modal-header"
    >
      <p className="text-primary flex items-center gap-2 text-sm">
        <IconComponent
          name="Settings"
          strokeWidth={ICON_STROKE_WIDTH}
          className="text-muted-foreground hover:text-foreground h-4 w-4"
        />
        Voice settings
      </p>
      <p className="text-mmd text-muted-foreground leading-4">
        Voice chat is powered by OpenAI. You can also add more voices with
        ElevenLabs.
      </p>
    </div>
  );
};

export default AudioSettingsHeader;
