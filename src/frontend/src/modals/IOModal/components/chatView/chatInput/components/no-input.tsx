import { Button } from "@/components/ui/button";
import Loading from "@/components/ui/loading";
import React, { useEffect, useRef, useState } from "react";
import IconComponent from "../../../../../../components/common/genericIconComponent";
import { ICON_STROKE_WIDTH } from "../../../../../../constants/constants";
import { cn } from "../../../../../../utils/utils";

interface NoInputViewProps {
  isBuilding: boolean;
  sendMessage: (args: { repeat: number }) => Promise<void>;
  stopBuilding: () => void;
}

const NoInputView: React.FC<NoInputViewProps> = ({
  isBuilding,
  sendMessage,
  stopBuilding,
}) => {
  return (
    <div className="flex h-full w-full flex-col items-center justify-center">
      <div className="border-input bg-muted flex w-full flex-col items-center justify-center gap-3 rounded-md border p-2 py-4">
        {!isBuilding ? (
          <Button
            data-testid="button-send"
            className="font-semibold"
            onClick={async () => {
              await sendMessage({
                repeat: 1,
              });
            }}
          >
            Run Flow
          </Button>
        ) : (
          <Button
            onClick={stopBuilding}
            data-testid="button-stop"
            unstyled
            className="form-modal-send-button bg-muted text-foreground hover:bg-secondary-hover dark:hover:bg-input cursor-pointer"
          >
            <div className="flex items-center gap-2 rounded-md text-sm font-medium">
              Stop
              <Loading className="h-4 w-4" />
            </div>
          </Button>
        )}

        <p className="text-muted-foreground">
          Add a{" "}
          <a
            className="underline underline-offset-4"
            target="_blank"
            href="https://docs.langflow.org/components-io#chat-input"
          >
            Chat Input
          </a>{" "}
          component to your flow to send messages.
        </p>
      </div>
    </div>
  );
};

export default NoInputView;
