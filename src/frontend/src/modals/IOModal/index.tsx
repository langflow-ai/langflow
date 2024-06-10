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
import { CHAT_FORM_DIALOG_SUBTITLE } from "../../constants/constants";
import { InputOutput } from "../../constants/enums";
import { getMessagesTable } from "../../controllers/API";
import useAlertStore from "../../stores/alertStore";
import useFlowStore from "../../stores/flowStore";
import useFlowsManagerStore from "../../stores/flowsManagerStore";
import { useMessagesStore } from "../../stores/messagesStore";
import { IOModalPropsType } from "../../types/components";
import { NodeDataType, NodeType } from "../../types/flow";
import { updateVerticesOrder } from "../../utils/buildUtils";
import { cn } from "../../utils/utils";
import BaseModal from "../baseModal";
import IOFieldView from "./components/IOFieldView";
import SessionView from "./components/SessionView";
import useRemoveSession from "./components/SessionView/hooks";
import ChatView from "./components/chatView";

export default function IOModal({
  children,
  open,
  setOpen,
  disable,
}: IOModalPropsType): JSX.Element {
  const allNodes = useFlowStore((state) => state.nodes);
  const setMessages = useMessagesStore((state) => state.setMessages);
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
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);

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
  const [sessions, setSessions] = useState<string[]>([]);
  const messages = useMessagesStore((state) => state.messages);
  const setColumns = useMessagesStore((state) => state.setColumns);
  const flowPool = useFlowStore((state) => state.flowPool);
  async function updateVertices() {
    return updateVerticesOrder(currentFlow!.id, null);
  }

  async function sendMessage({
    repeat = 1,
    files,
  }: {
    repeat: number;
    files?: string[];
  }): Promise<void> {
    if (isBuilding) return;
    setIsBuilding(true);
    setLockChat(true);
    setChatValue("");
    for (let i = 0; i < repeat; i++) {
      await buildFlow({
        input_value: chatValue,
        startNodeId: chatInput?.id,
        files: files,
        silent: true,
      }).catch((err) => {
        console.error(err);
        setLockChat(false);
      });
    }
    const { rows, columns } = await getMessagesTable("union", currentFlow!.id, [
      "index",
      "flow_id",
    ]);
    setMessages(rows);
    setColumns(columns);
    setLockChat(false);
    if (chatInput) {
      setNode(chatInput.id, (node: NodeType) => {
        const newNode = { ...node };

        newNode.data.node!.template["input_value"].value = chatValue;
        return newNode;
      });
    }
  }

  const { handleRemoveSession } = useRemoveSession(
    setSuccessData,
    setErrorData,
  );

  useEffect(() => {
    setSelectedTab(inputs.length > 0 ? 1 : outputs.length > 0 ? 2 : 0);
  }, [allNodes.length]);

  const flow_sessions = allNodes.map((node) => {
    if ((node.data as NodeDataType).node?.template["session_id"]) {
      return {
        id: node.id,
        session_id: (node.data as NodeDataType).node?.template["session_id"]
          .value,
      };
    }
  });

  useEffect(() => {
    setSelectedViewField(startView());
    if (haveChat) {
      getMessagesTable("union", currentFlow!.id, ["index", "flow_id"]).then(
        ({ rows, columns }) => {
          setMessages(rows);
          setColumns(columns);
        },
      );
    }
  }, [open]);

  useEffect(() => {
    const sessions = new Set<string>();
    messages.forEach((row) => {
      sessions.add(row.session_id);
    });
    setSessions(Array.from(sessions));
    sessions;
  }, [messages]);

  return (
    <BaseModal
      size={"md-thin"}
      open={open}
      setOpen={setOpen}
      disable={disable}
      onSubmit={() => sendMessage({ repeat: 1 })}
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
      <BaseModal.Content overflowHidden>
        <div className="flex h-full flex-col">
          <div className="flex-max-width h-full">
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
                    {haveChat && (
                      <TabsTrigger value={"0"}>Memories</TabsTrigger>
                    )}
                  </TabsList>
                </div>

                <TabsContent value={"1"} className="api-modal-tabs-content">
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
                <TabsContent value={"2"} className="api-modal-tabs-content">
                  {nodes
                    .filter((node) =>
                      outputs.some((output) => output.id === node.id),
                    )
                    .map((node, index) => {
                      const output = outputs.find(
                        (output) => output.id === node.id,
                      )!;
                      const textOutputValue =
                        (flowPool[node!.id] ?? [])[
                          (flowPool[node!.id]?.length ?? 1) - 1
                        ]?.data?.artifacts ?? "";
                      const disabled =
                        textOutputValue === "" ||
                        JSON.stringify(textOutputValue) === "{}";
                      return (
                        <div
                          className="file-component-accordion-div"
                          key={index}
                        >
                          <AccordionComponent
                            disabled={disabled}
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
                <TabsContent value={"0"} className="api-modal-tabs-content">
                  {sessions.map((session, index) => {
                    return (
                      <div
                        className="file-component-accordion-div cursor-pointer"
                        onClick={(event) => {
                          event.stopPropagation();
                          setSelectedViewField({
                            id: session,
                            type: "Session",
                          });
                        }}
                      >
                        <div className="flex w-full items-center justify-between gap-2 overflow-hidden border-b px-2 py-3.5 align-middle">
                          <ShadTooltip styleClasses="z-50" content={session}>
                            <div className="flex min-w-0">
                              <Badge
                                variant="gray"
                                size="md"
                                className="block truncate"
                              >
                                {session === currentFlow?.id
                                  ? "Default Session"
                                  : session}
                              </Badge>
                            </div>
                          </ShadTooltip>
                          <div className="flex shrink-0 items-center justify-center gap-2 align-middle">
                            <Button
                              variant="none"
                              size="icon"
                              onClick={(e) => {
                                e.preventDefault();
                                e.stopPropagation();
                                handleRemoveSession(session);
                                if (selectedViewField?.id === session)
                                  setSelectedViewField(undefined);
                              }}
                            >
                              <ShadTooltip
                                styleClasses="z-50"
                                content={"Delete"}
                              >
                                <div>
                                  <IconComponent
                                    name="Trash2"
                                    className="h-4 w-4"
                                  ></IconComponent>
                                </div>
                              </ShadTooltip>
                            </Button>
                            {/* <div>
                              <ShadTooltip
                                styleClasses="z-50"
                                content={
                                  flow_sessions.some(
                                    (f_session) =>
                                      f_session?.session_id === session,
                                  )
                                    ? "Active Session"
                                    : "Inactive Session"
                                }
                              >
                                <div
                                  className={cn(
                                    "h-2 w-2 rounded-full",
                                    flow_sessions.some(
                                      (f_session) =>
                                        f_session?.session_id === session,
                                    )
                                      ? "bg-status-green"
                                      : "bg-slate-500",
                                  )}
                                ></div>
                              </ShadTooltip>
                            </div> */}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </TabsContent>
              </Tabs>
            </div>
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
                    ) && (
                      <IOFieldView
                        type={InputOutput.INPUT}
                        left={false}
                        fieldType={selectedViewField.type!}
                        fieldId={selectedViewField.id!}
                      />
                    )}
                    {outputs.some(
                      (output) => output.id === selectedViewField.id,
                    ) && (
                      <IOFieldView
                        type={InputOutput.OUTPUT}
                        left={false}
                        fieldType={selectedViewField.type!}
                        fieldId={selectedViewField.id!}
                      />
                    )}
                    {sessions.some(
                      (session) => session === selectedViewField.id,
                    ) && (
                      <SessionView
                        rows={messages.filter(
                          (message) =>
                            message.session_id === selectedViewField.id,
                        )}
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
        <BaseModal.Footer
          submit={{
            label: "Run Flow",
            icon: (
              <IconComponent
                name={isBuilding ? "Loader2" : "Zap"}
                className={cn(
                  "h-4 w-4",
                  isBuilding
                    ? "animate-spin"
                    : "fill-current text-medium-indigo",
                )}
              />
            ),
          }}
        />
      ) : (
        <></>
      )}
    </BaseModal>
  );
}
