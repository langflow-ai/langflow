import React, { useEffect, useRef, useState } from "react";
import langflowLogo from "@/assets/LangflowLogoColor.svg";
import { useGetGeneratedPromptQuery } from "@/controllers/API/queries/assistant";
import { useGetFlowId } from "@/modals/IOModal/hooks/useGetFlowId";
import PromptModal from "@/modals/promptModal";
import useFlowStore from "@/stores/flowStore";
import { targetHandleType } from "@/types/flow";

interface AIButtonProps {
  compData: targetHandleType;
}

export const AIButton: React.FC<AIButtonProps> = ({ compData }) => {
  // const [promptValue, setPromptValue] = useState("");
  const { setSelectedCompData } = useFlowStore();
  const flowId = useGetFlowId();

  useEffect(() => {
    setSelectedCompData(compData);
  }, [compData, setSelectedCompData]);

  const { data, isFetching, refetch } = useGetGeneratedPromptQuery({
    compId: compData.id,
    flowId,
    fieldName: compData.fieldName,
  });

  const onButtonClick = async () => {
    setSelectedCompData(compData);
    const result = await refetch();
    console.log("_____________________________result", result);

    // setPromptValue(result.data);
  };

  return (
    <div className="relative flex items-center">
      {/* <PromptModal value={promptValue} setValue={setPromptValue}> */}
      <button
        onClick={onButtonClick}
        title="Langflow assistant"
        className="
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
        "
      >
        <img
          src={langflowLogo}
          alt="Langflow logo"
          className="w-3.5 h-3.5 object-contain"
        />
      </button>
      {/* </PromptModal> */}
    </div>
  );
};
