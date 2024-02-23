import { useEffect, useState } from "react";
import { CHAT_FORM_DIALOG_SUBTITLE } from "../../constants/constants";
import BaseModal from "../../modals/baseModal";
import useFlowStore from "../../stores/flowStore";
import { cn } from "../../utils/utils";
import AccordionComponent from "../AccordionComponent";
import IOInputField from "../IOInputField";
import IOOutputView from "../IOOutputView";
import IconComponent from "../genericIconComponent";
import NewChatView from "../newChatView";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";

export default function IOView({ children, open, setOpen }): JSX.Element {
  const inputs = useFlowStore((state) => state.inputs).filter(
    (input) => input.type !== "ChatInput"
  );
  const outputs = useFlowStore((state) => state.outputs).filter(
    (output) => output.type !== "ChatOutput"
  );
  const nodes = useFlowStore((state) => state.nodes).filter(
    (node) =>
      (inputs.some((input) => input.id === node.id) ||
        outputs.some((output) => output.id === node.id)) &&
      node.type !== "ChatInput" &&
      node.type !== "ChatOutput"
  );
  const haveChat = useFlowStore((state) => state.outputs).some(
    (output) => output.type === "ChatOutput"
  );
  const [selectedTab, setSelectedTab] = useState(
    inputs.length > 0 ? 1 : outputs.length > 0 ? 2 : 0
  );
  const [selectedViewField, setSelectedViewField] = useState<
    { type: string; id: string } | undefined
  >(undefined);

  useEffect(() => {
    setSelectedViewField(undefined);
    setSelectedTab(inputs.length > 0 ? 1 : outputs.length > 0 ? 2 : 0);
  }, [inputs.length, outputs.length]);

  return (
    <BaseModal
      size={haveChat ? "large" : "small"}
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
        <div className="flex-max-width mt-2 h-[80vh]">
          {selectedTab !== 0 && (
            <div
              className={cn(
                "mr-6 flex h-full w-2/6 flex-shrink-0 flex-col justify-start overflow-auto scrollbar-hide",
                haveChat ? "w-2/6" : "w-full"
              )}
            >
              <div className="flex w-full items-center justify-between py-2">
                <div className="flex items-start gap-4">
                  {inputs.length > 0 && (
                    <Button
                      onClick={() => setSelectedTab(1)}
                      variant={selectedTab === 1 ? "primary" : "secondary"}
                    >
                      <IconComponent
                        name="FormInput"
                        className=" file-component-variable"
                      />
                      <span className="file-component-variables-span text-md">
                        Inputs
                      </span>
                    </Button>
                  )}
                  {outputs.length > 0 && (
                    <Button
                      onClick={() => setSelectedTab(2)}
                      variant={selectedTab === 2 ? "primary" : "secondary"}
                    >
                      <IconComponent
                        name="ChevronRightSquare"
                        className=" file-component-variable"
                      />
                      <span className="file-component-variables-span text-md">
                        Outputs
                      </span>
                    </Button>
                  )}
                </div>
                {selectedViewField && haveChat && (
                  <Button
                    onClick={() => setSelectedViewField(undefined)}
                    variant="outline"
                    key={"chat"}
                    className="self-end px-2.5"
                  >
                    <IconComponent
                      name="MessageSquareMore"
                      className="h-5 w-5"
                    />
                  </Button>
                )}
              </div>
              <div className="mx-2 mb-2 mt-4 flex items-center gap-2 font-semibold">
                {selectedTab === 1 && (
                  <>
                    <IconComponent name={"FormInput"} />
                    Text Inputs
                  </>
                )}
                {selectedTab === 2 && (
                  <>
                    <IconComponent name={"ChevronRightSquare"} />
                    Prompt Outputs
                  </>
                )}
              </div>
              {nodes
                .filter((node) =>
                  selectedTab === 1
                    ? inputs.some((input) => input.id === node.id)
                    : outputs.some((output) => output.id === node.id)
                )
                .map((node, index) => {
                  const input =
                    selectedTab === 1
                      ? inputs.find((input) => input.id === node.id)!
                      : outputs.find((output) => output.id === node.id)!;
                  return (
                    <div className="file-component-accordion-div" key={index}>
                      <AccordionComponent
                        trigger={
                          <div className="file-component-badge-div">
                            <Badge variant="gray" size="md">
                              {input.id}
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
                            {input &&
                              (selectedTab === 1 ? (
                                <IOInputField
                                  inputType={input.type}
                                  inputId={input.id}
                                />
                              ) : (
                                <IOOutputView
                                  outputType={input.type}
                                  outputId={input.id}
                                />
                              ))}
                          </div>
                        </div>
                      </AccordionComponent>
                    </div>
                  );
                })}
            </div>
          )}

          {haveChat ? (
            selectedViewField ? (
              inputs.some((input) => input.id === selectedViewField.id) ? (
                <IOInputField
                  inputType={selectedViewField.type!}
                  inputId={selectedViewField.id!}
                />
              ) : (
                <IOOutputView
                  outputType={selectedViewField.type!}
                  outputId={selectedViewField.id!}
                />
              )
            ) : (
              <NewChatView />
            )
          ) : (
            <div className="absolute bottom-8 right-8">
              <Button className="px-3">
                <IconComponent name="Play" className="h-6 w-6" />
              </Button>
            </div>
          )}
        </div>
      </BaseModal.Content>
    </BaseModal>
  );
}
