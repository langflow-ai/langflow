import { useEffect, useState } from "react";
import AccordionComponent from "../../components/accordionComponent";
import IconComponent from "../../components/genericIconComponent";
import ShadTooltip from "../../components/shadTooltipComponent";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "../../components/ui/tabs";
import {
  CHAT_FORM_DIALOG_SUBTITLE,
  OUTPUTS_MODAL_TITLE,
  TEXT_INPUT_MODAL_TITLE,
} from "../../constants/constants";
import { InputOutput } from "../../constants/enums";
import useFlowStore from "../../stores/flowStore";
import useFlowsManagerStore from "../../stores/flowsManagerStore";
import { IOModalPropsType } from "../../types/components";
import { NodeType } from "../../types/flow";
import { updateVerticesOrder } from "../../utils/buildUtils";
import { cn } from "../../utils/utils";
import BaseModal from "../baseModal";
import IOFieldView from "./components/IOFieldView";
import ChatView from "./components/chatView";

export default function IOModal({
  children,
  open,
  setOpen,
  disable,
}: IOModalPropsType): JSX.Element {
  const allNodes = useFlowStore((state) => state.nodes);
  const inputs = useFlowStore((state) => state.inputs).filter(
    (input) => input.type !== "ChatInput",
  );
  const chatInput = useFlowStore((state) => state.inputs).find(
    (input) => input.type === "ChatInput",
  );
  const outputs = useFlowStore((state) => state.outputs).filter(
    (output) => output.type !== "ChatOutput",
  );
  const chatOutput = useFlowStore((state) => state.outputs).find(
    (output) => output.type === "ChatOutput",
  );
  const nodes = useFlowStore((state) => state.nodes).filter(
    (node) =>
      inputs.some((input) => input.id === node.id) ||
      outputs.some((output) => output.id === node.id),
  );
  const haveChat = chatInput || chatOutput;
  const [selectedTab, setSelectedTab] = useState(
    inputs.length > 0 ? 1 : outputs.length > 0 ? 2 : 0,
  );

  function startView() {
    if (!chatInput && !chatOutput) {
      if (inputs.length > 0) {
        return inputs[0];
      } else {
        return outputs[0];
      }
    } else {
      return undefined;
    }
  }

  const [selectedViewField, setSelectedViewField] = useState<
    { type: string; id: string } | undefined
  >(startView());

  const buildFlow = useFlowStore((state) => state.buildFlow);
  const setIsBuilding = useFlowStore((state) => state.setIsBuilding);
  const [lockChat, setLockChat] = useState(false);
  const [chatValue, setChatValue] = useState("");
  const isBuilding = useFlowStore((state) => state.isBuilding);
  const currentFlow = useFlowsManagerStore((state) => state.currentFlow);
  const setNode = useFlowStore((state) => state.setNode);

  async function updateVertices() {
    return updateVerticesOrder(currentFlow!.id, null);
  }

  async function sendMessage(count = 1): Promise<void> {
    if (isBuilding) return;
    setIsBuilding(true);
    setLockChat(true);
    setChatValue("");
    for (let i = 0; i < count; i++) {
      await buildFlow({
        input_value: chatValue,
        startNodeId: chatInput?.id,
      }).catch((err) => {
        console.error(err);
        setLockChat(false);
      });
    }
    setLockChat(false);
    if (chatInput) {
      setNode(chatInput.id, (node: NodeType) => {
        const newNode = { ...node };
        newNode.data.node!.template["input_value"].value = chatValue;
        return newNode;
      });
    }
  }

  useEffect(() => {
    setSelectedTab(inputs.length > 0 ? 1 : outputs.length > 0 ? 2 : 0);
  }, [allNodes.length]);

  useEffect(() => {
    setSelectedViewField(startView());
  }, [open]);

  return (
    <BaseModal
      size={selectedTab === 0 ? "sm-thin" : "md-thin"}
      open={open}
      setOpen={setOpen}
      disable={disable}
    >
      <BaseModal.Trigger>{children}</BaseModal.Trigger>
      {/* TODO ADAPT TO ALL TYPES OF INPUTS AND OUTPUTS */}
      <BaseModal.Header description={CHAT_FORM_DIALOG_SUBTITLE}>
        <div className="flex items-center">
          <span className="pr-2">Playground</span>
          <IconComponent
            name="BotMessageSquareIcon"
            className="h-6 w-6 pl-1 text-foreground"
            aria-hidden="true"
          />
        </div>
      </BaseModal.Header>
      <BaseModal.Content>
        <div className="flex h-full flex-col ">
          <div className="flex-max-width h-full">
            {selectedTab !== 0 && (
              <div
                className={cn(
                  "mr-6 flex h-full w-2/6 flex-shrink-0 flex-col justify-start transition-all duration-300",
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
                      {TEXT_INPUT_MODAL_TITLE}
                    </div>
                    {nodes
                      .filter((node) =>
                        inputs.some((input) => input.id === node.id),
                      )
                      .map((node, index) => {
                        const input = inputs.find(
                          (input) => input.id === node.id,
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
                                    content={input.id}
                                    styleClasses="z-50"
                                  >
                                    <div>
                                      <Badge variant="gray" size="md">
                                        {node.data.node.display_name}
                                      </Badge>
                                    </div>
                                  </ShadTooltip>
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
                                </div>
                              }
                              key={index}
                              keyValue={input.id}
                            >
                              <div className="file-component-tab-column">
                                <div className="">
                                  {input && (
                                    <IOFieldView
                                      type={InputOutput.INPUT}
                                      left={true}
                                      fieldType={input.type}
                                      fieldId={input.id}
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
                      <IconComponent className="h-4 w-4" name={"Type"} />
                      {OUTPUTS_MODAL_TITLE}
                    </div>
                    {nodes
                      .filter((node) =>
                        outputs.some((output) => output.id === node.id),
                      )
                      .map((node, index) => {
                        const output = outputs.find(
                          (output) => output.id === node.id,
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
                                        {node.data.node.display_name}
                                      </Badge>
                                    </div>
                                  </ShadTooltip>
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
                                </div>
                              }
                              key={index}
                              keyValue={output.id}
                            >
                              <div className="file-component-tab-column">
                                <div className="">
                                  {output && (
                                    <IOFieldView
                                      type={InputOutput.OUTPUT}
                                      left={true}
                                      fieldType={output.type}
                                      fieldId={output.id}
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

            <div className="flex h-full min-w-96 flex-grow">
              {selectedViewField && (
                <div
                  className={cn(
                    "flex h-full w-full flex-col items-start gap-4 pt-4",
                    !selectedViewField ? "hidden" : "",
                  )}
                >
                  <div className="font-xl flex items-center justify-center gap-3 font-semibold">
                    {haveChat && (
                      <button onClick={() => setSelectedViewField(undefined)}>
                        <IconComponent
                          name={"ArrowLeft"}
                          className="h-6 w-6"
                        ></IconComponent>
                      </button>
                    )}
                    {
                      nodes.find((node) => node.id === selectedViewField.id)
                        ?.data.node.display_name
                    }
                  </div>
                  <div className="h-full w-full">
                    {inputs.some(
                      (input) => input.id === selectedViewField.id,
                    ) ? (
                      <IOFieldView
                        type={InputOutput.INPUT}
                        left={false}
                        fieldType={selectedViewField.type!}
                        fieldId={selectedViewField.id!}
                      />
                    ) : (
                      <IOFieldView
                        type={InputOutput.OUTPUT}
                        left={false}
                        fieldType={selectedViewField.type!}
                        fieldId={selectedViewField.id!}
                      />
                    )}
                  </div>
                </div>
              )}
              <div
                className={cn(
                  "flex h-full w-full",
                  selectedViewField ? "hidden" : "",
                )}
              >
                {haveChat ? (
                  <ChatView
                    sendMessage={sendMessage}
                    chatValue={chatValue}
                    setChatValue={setChatValue}
                    lockChat={lockChat}
                    setLockChat={setLockChat}
                  />
                ) : (
                  <span className="flex h-full w-full items-center justify-center font-thin text-muted-foreground">
                    Select an IO component to view
                  </span>
                )}
              </div>
            </div>
          </div>
        </div>
      </BaseModal.Content>
      {!haveChat ? (
        <BaseModal.Footer>
          <div className="flex w-full justify-end  pt-2">
            <Button
              variant={"outline"}
              className="flex gap-2 px-3"
              onClick={() => sendMessage(1)}
            >
              <IconComponent
                name={isBuilding ? "Loader2" : "Zap"}
                className={cn(
                  "h-4 w-4",
                  isBuilding
                    ? "animate-spin"
                    : "fill-current text-medium-indigo",
                )}
              />
              Run Flow
            </Button>
          </div>
        </BaseModal.Footer>
      ) : (
        <></>
      )}
    </BaseModal>
  );
}
