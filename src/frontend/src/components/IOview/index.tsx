import { useEffect, useState } from "react";
import {
  CHAT_FORM_DIALOG_SUBTITLE,
  outputsModalTitle,
  textInputModalTitle,
} from "../../constants/constants";
import BaseModal from "../../modals/baseModal";
import useFlowStore from "../../stores/flowStore";
import useFlowsManagerStore from "../../stores/flowsManagerStore";
import { updateVerticesOrder } from "../../utils/buildUtils";
import { cn } from "../../utils/utils";
import AccordionComponent from "../AccordionComponent";
import IOInputField from "../IOInputField";
import IOOutputView from "../IOOutputView";
import ShadTooltip from "../ShadTooltipComponent";
import IconComponent from "../genericIconComponent";
import NewChatView from "../newChatView";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../ui/tabs";

export default function IOView({ children, open, setOpen }): JSX.Element {
  const inputs = useFlowStore((state) => state.inputs).filter(
    (input) => input.type !== "ChatInput"
  );
  const chatInput = useFlowStore((state) => state.inputs).find(
    (input) => input.type === "ChatInput"
  );
  const outputs = useFlowStore((state) => state.outputs).filter(
    (output) => output.type !== "ChatOutput"
  );
  const chatOutput = useFlowStore((state) => state.outputs).find(
    (output) => output.type === "ChatOutput"
  );
  const nodes = useFlowStore((state) => state.nodes).filter(
    (node) =>
      inputs.some((input) => input.id === node.id) ||
      outputs.some((output) => output.id === node.id)
  );
  const haveChat = chatInput || chatOutput;
  const [selectedTab, setSelectedTab] = useState(
    inputs.length > 0 ? 1 : outputs.length > 0 ? 2 : 0
  );
  const [selectedViewField, setSelectedViewField] = useState<
    { type: string; id: string } | undefined
  >(undefined);

  const buildFlow = useFlowStore((state) => state.buildFlow);
  const setIsBuilding = useFlowStore((state) => state.setIsBuilding);
  const [lockChat, setLockChat] = useState(false);
  const [chatValue, setChatValue] = useState("");
  const isBuilding = useFlowStore((state) => state.isBuilding);
  const currentFlow = useFlowsManagerStore((state) => state.currentFlow);

  async function updateVertices() {
    return updateVerticesOrder(currentFlow!.id, null);
  }

  useEffect(() => {
    if (open) {
      updateVertices();
    }
  }, [open, currentFlow]);

  async function sendMessage(count = 1): Promise<void> {
    if (isBuilding) return;
    setIsBuilding(true);
    setLockChat(true);
    setChatValue("");
    for (let i = 0; i < count; i++) {
      await buildFlow({ input_value: chatValue }).catch((err) => {
        console.error(err);
        setLockChat(false);
      });
    }
    setLockChat(false);
  }

  useEffect(() => {
    setSelectedViewField(undefined);
    setSelectedTab(inputs.length > 0 ? 1 : outputs.length > 0 ? 2 : 0);
  }, [inputs.length, outputs.length]);

  return (
    <BaseModal
      size={haveChat ? (selectedTab === 0 ? "large-thin" : "large") : "small"}
      open={open}
      setOpen={setOpen}
    >
      <BaseModal.Trigger>{children}</BaseModal.Trigger>
      {/* TODO ADAPT TO ALL TYPES OF INPUTS AND OUTPUTS */}
      <BaseModal.Header description={CHAT_FORM_DIALOG_SUBTITLE}>
        <div className="flex items-center">
          <span className="pr-2">Chat</span>
          <IconComponent
            name="prompts"
            className="h-6 w-6 pl-1 text-foreground"
            aria-hidden="true"
          />
        </div>
      </BaseModal.Header>
      <BaseModal.Content>
        <div className="flex h-full flex-col">
          <div className="flex-max-width mt-2 h-full">
            {selectedTab !== 0 && (
              <div
                className={cn(
                  "mr-6 flex h-full w-2/6 flex-shrink-0 flex-col justify-start",
                  haveChat ? "w-2/6" : "w-full"
                )}
              >
                <Tabs
                  value={selectedTab.toString()}
                  className={
                    "flex h-full flex-col overflow-y-auto rounded-md border bg-muted text-center custom-scroll"
                  }
                  onValueChange={(value) => {
                    setSelectedTab(Number(value));
                  }}
                >
                  <div className="api-modal-tablist-div">
                    <TabsList>
                      {inputs.length > 0 && (
                        <TabsTrigger value={"1"}>Inputs</TabsTrigger>
                      )}
                      {outputs.length > 0 && (
                        <TabsTrigger value={"2"}>Outputs</TabsTrigger>
                      )}
                    </TabsList>
                  </div>

                  <TabsContent
                    value={"1"}
                    className="api-modal-tabs-content mt-4"
                  >
                    <div className="mx-2 mb-2 flex items-center gap-2 text-sm font-bold">
                      <IconComponent className="h-4 w-4" name={"Type"} />
                      {textInputModalTitle}
                    </div>
                    {nodes
                      .filter((node) =>
                        inputs.some((input) => input.id === node.id)
                      )
                      .map((node, index) => {
                        const input = inputs.find(
                          (input) => input.id === node.id
                        )!;
                        return (
                          <div
                            className="file-component-accordion-div"
                            key={index}
                          >
                            <AccordionComponent
                              trigger={
                                <div className="file-component-badge-div">
                                  <Badge variant="gray" size="md">
                                    {node.data.node.display_name}
                                  </Badge>
                                  {haveChat && (
                                    <div
                                      className="-mb-1 pr-4"
                                      onClick={(event) => {
                                        event.stopPropagation();
                                        setSelectedViewField(input);
                                      }}
                                    >
                                      <IconComponent
                                        className="h-4 w-4"
                                        name="ExternalLink"
                                      ></IconComponent>
                                    </div>
                                  )}
                                </div>
                              }
                              key={index}
                              keyValue={input.id}
                            >
                              <div className="file-component-tab-column">
                                <div className="">
                                  {input && (
                                    <IOInputField
                                      inputType={input.type}
                                      inputId={input.id}
                                    />
                                  )}
                                </div>
                              </div>
                            </AccordionComponent>
                          </div>
                        );
                      })}
                  </TabsContent>
                  <TabsContent
                    value={"2"}
                    className="api-modal-tabs-content mt-4"
                  >
                    <div className="mx-2 mb-2 flex items-center gap-2 text-sm font-bold">
                      <IconComponent className="h-4 w-4" name={"FileType2"} />
                      {outputsModalTitle}
                    </div>
                    {nodes
                      .filter((node) =>
                        outputs.some((output) => output.id === node.id)
                      )
                      .map((node, index) => {
                        const output = outputs.find(
                          (output) => output.id === node.id
                        )!;
                        return (
                          <div
                            className="file-component-accordion-div"
                            key={index}
                          >
                            <AccordionComponent
                              trigger={
                                <div className="file-component-badge-div">
                                  <ShadTooltip
                                    content={output.id}
                                    styleClasses="z-50"
                                  >
                                    <div>
                                      <Badge variant="gray" size="md">
                                        {output.displayName}
                                      </Badge>
                                    </div>
                                  </ShadTooltip>
                                  {haveChat && (
                                    <div
                                      className="-mb-1 pr-4"
                                      onClick={(event) => {
                                        event.stopPropagation();
                                        setSelectedViewField(output);
                                      }}
                                    >
                                      <IconComponent
                                        className="h-4 w-4"
                                        name="ExternalLink"
                                      ></IconComponent>
                                    </div>
                                  )}
                                </div>
                              }
                              key={index}
                              keyValue={output.id}
                            >
                              <div className="file-component-tab-column">
                                <div className="">
                                  {output && (
                                    <IOOutputView
                                      outputType={output.type}
                                      outputId={output.id}
                                    />
                                  )}
                                </div>
                              </div>
                            </AccordionComponent>
                          </div>
                        );
                      })}
                  </TabsContent>
                </Tabs>
              </div>
            )}

            {haveChat ? (
              <div className="flex h-full w-full">
                {selectedViewField && (
                  <div
                    className={cn(
                      "flex h-full w-full flex-col items-start gap-4 p-4",
                      !selectedViewField ? "hidden" : ""
                    )}
                  >
                    <div className="font-xl flex items-center justify-center gap-3 font-semibold">
                      <button onClick={() => setSelectedViewField(undefined)}>
                        <IconComponent
                          name={"ArrowLeft"}
                          className="h-6 w-6"
                        ></IconComponent>
                      </button>
                      {selectedViewField.type}
                    </div>
                    <div className="h-full w-full">
                      {inputs.some(
                        (input) => input.id === selectedViewField.id
                      ) ? (
                        <IOInputField
                          inputType={selectedViewField.type!}
                          inputId={selectedViewField.id!}
                        />
                      ) : (
                        <IOOutputView
                          outputType={selectedViewField.type!}
                          outputId={selectedViewField.id!}
                        />
                      )}
                    </div>
                  </div>
                )}
                <div
                  className={cn(
                    "flex h-full w-full",
                    selectedViewField ? "hidden" : ""
                  )}
                >
                  <NewChatView
                    sendMessage={sendMessage}
                    chatValue={chatValue}
                    setChatValue={setChatValue}
                    lockChat={lockChat}
                    setLockChat={setLockChat}
                  />
                </div>
              </div>
            ) : (
              <div className="absolute bottom-8 right-8"></div>
            )}
          </div>
        </div>
      </BaseModal.Content>
      <BaseModal.Footer>
        {!haveChat && (
          <div className="flex w-full justify-end pt-6">
            <Button
              variant={"outline"}
              className="flex gap-2 px-3"
              onClick={() => sendMessage(1)}
            >
              <IconComponent
                name={isBuilding ? "Loader2" : "Play"}
                className={cn(
                  "h-4 w-4",
                  isBuilding
                    ? "animate-spin"
                    : "fill-current text-medium-indigo"
                )}
              />
              Run Flow
            </Button>
          </div>
        )}
      </BaseModal.Footer>
    </BaseModal>
  );
}
