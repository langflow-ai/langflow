import React, { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import langflowLogo from "@/assets/LangflowLogoColor.svg";
import { handleOnNewValueType } from "@/CustomNodes/hooks/use-handle-new-value";
import { useGetSystemMessageGenQuery } from "@/controllers/API/queries/assistant";
import { useGetFlowId } from "@/modals/IOModal/hooks/useGetFlowId";
import useAssistantManagerStore from "@/stores/assistantManagerStore";
import { useFolderStore } from "@/stores/foldersStore";
import { targetHandleType } from "@/types/flow";
import ForwardedIconComponent from "../genericIconComponent";

interface AssistantButtonProps {
  type: "field" | "flow" | "project" | "header";
  compData?: targetHandleType;
  inputValue?: string;
  handleOnNewValue?: handleOnNewValueType;
}

export const AssistantButton: React.FC<AssistantButtonProps> = ({
  type,
  compData,
  inputValue,
  handleOnNewValue,
}) => {
  const { assistantSidebarOpen, setAssistantSidebarOpen, setSelectedCompData } =
    useAssistantManagerStore();
  const flowId = useGetFlowId();
  const { folderId } = useParams();
  const myCollectionId = useFolderStore((state) => state.myCollectionId);
  const projectId = folderId ?? myCollectionId ?? "";

  // timer
  const [elapsedTime, setElapsedTime] = useState(0);
  const [clicked, setClicked] = useState(false);

  const { isFetching, refetch } = useGetSystemMessageGenQuery({
    compId: compData?.id,
    flowId,
    fieldName: compData?.fieldName,
    inputValue,
  });

  function getButtonClassName() {
    let className;
    switch (type) {
      case "field":
        className = `
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
        `;
        break;
      case "header":
        className = "mr-1 flex h-8 w-8 items-center";
        break;
      case "flow":
        className = "";
        break;
      case "project":
      default:
        className = "";
    }
    return className;
  }

  function getIconClassName() {
    let className;
    switch (type) {
      case "field":
        className = "w-3.5 h-3.5 object-contain";
        break;
      case "header":
        className = "h-5 w-5";
        break;
      case "flow":
        className = "";
        break;
      case "project":
      default:
        className = "";
    }
    return className;
  }

  useEffect(() => {
    let interval: NodeJS.Timeout | null = null;

    if (isFetching) {
      setElapsedTime(0);
      interval = setInterval(() => {
        setElapsedTime((prev) => prev + 1);
      }, 1000);
    } else if (!isFetching) {
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
    switch (type) {
      case "field": {
        setSelectedCompData(compData);
        setClicked(true);
        // we use result instead of data because data is undefined on first call
        const result = await refetch();
        handleOnNewValue({
          value:
            result.data?.data?.outputs[0]?.outputs[0]?.outputs?.message
              ?.message,
        });
        break;
      }
      case "header":
        setAssistantSidebarOpen(!assistantSidebarOpen);
        break;
      default:
        break;
    }
  };

  return (
    <div className="relative flex items-center">
      <button
        onClick={onButtonClick}
        title="Langflow assistant"
        className={getButtonClassName()}
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
            className={getIconClassName()}
          />
        )}
      </button>
      {clicked && type === "field" && (
        <span className="text-xs text-muted-foreground">{elapsedTime}s</span>
      )}
    </div>
  );
};
