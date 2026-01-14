import React, { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { handleOnNewValueType } from "@/CustomNodes/hooks/use-handle-new-value";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { useAgenticPromptQuery } from "@/controllers/API/queries/assistant/use-agentic-prompt";
import { useGetNextSuggestedComponentQuery } from "@/controllers/API/queries/assistant/use-suggest-next-component";
import { useGetFlowId } from "@/modals/IOModal/hooks/useGetFlowId";
import useAssistantManagerStore from "@/stores/assistantManagerStore";
import { useFolderStore } from "@/stores/foldersStore";
import { targetHandleType } from "@/types/flow";
import Pill from "./pills";

interface AssistantNudgesProps {
  type: "field" | "flow" | "project" | "header";
  setNudgesOpen;
  handleOnNewValue: handleOnNewValueType;
}

export const AssistantNudges: React.FC<AssistantNudgesProps> = ({
  type,
  setNudgesOpen,
  handleOnNewValue,
}) => {
  const flowId = useGetFlowId();
  const { folderId } = useParams();
  const myCollectionId = useFolderStore((state) => state.myCollectionId);
  const projectId = folderId ?? myCollectionId ?? "";
  const [selectedMode, setSelectedMode] = useState("PROMPT");
  const [userInput, setUserInput] = useState("");
  const [promptOutput, setPromptOutput] = useState("Generate a Prompt");
  const [nudegsLoading, setNudgesLoading] = useState(true);
  const [componentNudges, setComponentNudges] = useState(null);
  const { selectedCompData } = useAssistantManagerStore();

  // timer
  const [elapsedTime, setElapsedTime] = useState(0);
  const [generatePromptClicked, setGeneratePromptClicked] = useState(false);

  const { isFetching: isFetchingPrompt, refetch: prompt } =
    useAgenticPromptQuery({
      compId: selectedCompData?.id,
      flowId,
      fieldName: selectedCompData?.fieldName,
      inputValue: userInput,
    });

  const {
    isFetching: isFetchingNextSuggestComponents,
    refetch: suggestedComponents,
  } = useGetNextSuggestedComponentQuery({
    compId: selectedCompData?.id,
    flowId,
    fieldName: selectedCompData?.fieldName,
    inputValue: userInput,
  });

  useEffect(() => {
    let interval: NodeJS.Timeout | null = null;

    if (isFetchingPrompt) {
      setElapsedTime(0);
      interval = setInterval(() => {
        setElapsedTime((prev) => prev + 1);
      }, 1000);
    } else if (!isFetchingPrompt) {
      // Cleanup when done
      clearInterval(interval!);
    }

    return () => {
      if (interval) clearInterval(interval);
    };
  }, [isFetchingPrompt]);

  useEffect(() => {
    const result = async () => {
      setNudgesLoading(true);
      return await suggestedComponents();
    };
    result().then((nudges) => {
      setComponentNudges(
        JSON.parse(nudges.data.data.outputs[0].outputs[0].messages[0].message),
      );
      setNudgesLoading(false);
    });
  }, []);

  const onGenButtonClick = async () => {
    switch (type) {
      case "field": {
        setGeneratePromptClicked(true);
        const result = await prompt();
        setPromptOutput(result.data?.data?.result);
        setGeneratePromptClicked(false);
        break;
      }
      case "header":
      default:
        break;
    }
  };
  const onReplaceButtonClick = async () => {
    switch (type) {
      case "field": {
        handleOnNewValue({
          value: promptOutput,
        });
        setNudgesOpen(false);
        break;
      }
      case "header":
      default:
        break;
    }
  };

  return (
    <>
      <Tabs value={selectedMode} onValueChange={setSelectedMode}>
        <TabsList>
          <TabsTrigger data-testid="prompt-tab" value="PROMPT">
            Prompt
          </TabsTrigger>
          <TabsTrigger data-testid="component-tab" value="COMPONENT">
            Component
          </TabsTrigger>
        </TabsList>
        <div className="overflow-hidden rounded-lg border border-border">
          <TabsContent value="PROMPT">
            <div className="flex flex-col gap-2">
              <Label className="!text-mmd">TODO USER INPUT HELPER TEXT</Label>
              <Textarea
                value={userInput}
                data-testid="prompt-user-input"
                onChange={(e) => setUserInput(e.target.value)}
                className="min-h-[50px] font-mono text-mmd"
                placeholder="Prompt Mode"
              />
              <Label className="!text-mmd">
                TODO PROMPT OUTPUT HELPER TEXT
              </Label>
              <Textarea
                value={promptOutput}
                data-testid="prompt-user-input"
                onChange={(e) => setPromptOutput(e.target.value)}
                className="min-h-[50px] font-mono text-mmd"
                placeholder="Prompt Mode"
              />
              <div>
                <Button
                  variant="secondary"
                  onClick={onGenButtonClick}
                  disabled={generatePromptClicked}
                >
                  Generate Prompt
                  {generatePromptClicked && type === "field" && (
                    <span className="text-xs text-muted-foreground">
                      {elapsedTime}s
                    </span>
                  )}
                </Button>
                <Button variant="destructive" onClick={onReplaceButtonClick}>
                  Replace with Prompt
                </Button>
              </div>
            </div>
          </TabsContent>
          <TabsContent value="COMPONENT">
            <div className="flex flex-col gap-2">
              <Label className="!text-mmd">TODO COMPONENT HELPER TEXT</Label>
              <Textarea
                value={userInput}
                data-testid="component-user-input"
                onChange={(e) => setUserInput(e.target.value)}
                className="min-h-[25px] font-mono text-mmd"
                placeholder="Component Mode"
              />
              {!nudegsLoading &&
                componentNudges?.nudges.map((nudge) => {
                  return (
                    <Pill nudge={nudge} setNudgesOpen={setNudgesOpen}></Pill>
                  );
                })}
            </div>
          </TabsContent>
        </div>
      </Tabs>
    </>
  );
};
