import React, { useEffect, useRef, useState } from "react";
import langflowLogo from "@/assets/LangflowLogoColor.svg";
import { handleOnNewValueType } from "@/CustomNodes/hooks/use-handle-new-value";
import { useGetGeneratedPromptQuery } from "@/controllers/API/queries/assistant";
import { useGetFlowId } from "@/modals/IOModal/hooks/useGetFlowId";
import useAssistantManagerStore from "@/stores/assistantManagerStore";
import { targetHandleType } from "@/types/flow";
import ForwardedIconComponent from "../genericIconComponent";

interface AssistantButtonProps {
  compData: targetHandleType;
  handleOnNewValue: handleOnNewValueType;
}

export const AssistantButton: React.FC<AssistantButtonProps> = ({
  compData,
  handleOnNewValue,
}) => {
  const { setSelectedCompData } = useAssistantManagerStore();
  const flowId = useGetFlowId();

  // timer
  const [elapsedTime, setElapsedTime] = useState(0);
  const [clicked, setClicked] = useState(false);

  const { data, isFetching, refetch } = useGetGeneratedPromptQuery({
    compId: compData.id,
    flowId,
    fieldName: compData.fieldName,
  });

  useEffect(() => {
    let interval: NodeJS.Timeout | null = null;

    if (isFetching) {
      setElapsedTime(0);
      interval = setInterval(() => {
        setElapsedTime((prev) => prev + 1);
      }, 1000);
    } else if (!isFetching && elapsedTime > 0) {
      // Cleanup when done
      clearInterval(interval!);
    }

    return () => {
      if (interval) clearInterval(interval);
    };
  }, [isFetching]);

  useEffect(() => {
    setSelectedCompData(compData);
  }, [compData, setSelectedCompData]);

  const onButtonClick = async () => {
    setSelectedCompData(compData);
    setClicked(true);
    // we use result instaed of data because data is undefined on first call
    const result = await refetch();
    handleOnNewValue({
      value:
        result.data?.data?.outputs[0]?.outputs[0]?.outputs?.message?.message,
    });
  };

  return (
    <div className="relative flex items-center">
      <button
        onClick={onButtonClick}
        title="Langflow assistant"
        className={`
          inline-flex items-center justify-center
          w-5 h-5
          rounded-md
          text-muted-foreground
          hover:text-primary
          hover:bg-muted/70
          transition-colors duration-150
          focus-visible:outline-none
          focus-visible:ring-1
          focus-visible:ring-ring
          focus-visible:ring-offset-1
          focus-visible:ring-offset-background
          ${isFetching ? "opacity-70 cursor-not-allowed" : ""}
        `}
      >
        {isFetching ? (
          <ForwardedIconComponent
            name={"Loader2"}
            className={
              "animate-spin w-3.5 h-3.5 text-primary cursor-not-allowed"
            }
          />
        ) : (
          <img
            src={langflowLogo}
            alt="Langflow logo"
            className="w-3.5 h-3.5 object-contain"
          />
        )}
      </button>
      {clicked && (
        <span className="text-xs text-muted-foreground">{elapsedTime}s</span>
      )}
    </div>
  );
};
