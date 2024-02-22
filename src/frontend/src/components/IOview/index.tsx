import { ReactNode, useState } from "react";
import { CHAT_FORM_DIALOG_SUBTITLE } from "../../constants/constants";
import BaseModal from "../../modals/baseModal";
import useFlowStore from "../../stores/flowStore";
import { NodeType } from "../../types/flow";
import { isInputType, isOutputType } from "../../utils/reactflowUtils";
import { cn } from "../../utils/utils";
import AccordionComponent from "../AccordionComponent";
import IOInputField from "../IOInputField";
import IOOutputView from "../IOOutputView";
import IconComponent from "../genericIconComponent";
import NewChatView from "../newChatView";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";

export default function IOView({ children, open, setOpen }): JSX.Element {
  const inputs = useFlowStore((state) => state.inputs);
  const outputs = useFlowStore((state) => state.outputs);
  const inputIds = inputs.map((obj) => obj.id);
  const outputIds = outputs.map((obj) => obj.id);
  const nodes = useFlowStore((state) => state.nodes);
  const setNode = useFlowStore((state) => state.setNode);
  const categories = getCategories();
  const [selectedCategory, setSelectedCategory] = useState<number>(0);
  const [showChat, setShowChat] = useState<boolean>(false);
  const [selectedView, setSelectedView] = useState<{
    type: string;
    id?: string;
  }>(handleInitialView());

  type CategoriesType = { name: string; icon: string };

  function handleInitialView() {
    if (
      outputs.map((output) => output.type).includes("ChatOutput") ||
      inputs.map((input) => input.type).includes("ChatInput")
    ) {
      return { type: "ChatOutput" };
    }
    return { type: "" };
  }

  function getCategories() {
    const categories: CategoriesType[] = [];
    if (inputs.filter((input) => input.type !== "ChatInput").length > 0)
      categories.push({ name: "Inputs", icon: "TextCursorInput" });
    if (outputs.filter((output) => output.type !== "ChatOutput").length > 0)
      categories.push({ name: "Outputs", icon: "TerminalSquare" });
    return categories;
  }

  function handleSelectChange(): ReactNode {
    const { type, id } = selectedView;
    if (type === "ChatOutput") return <NewChatView />;
    if (isInputType(type))
      return <IOInputField inputId={id!} inputType={type} />;
    if (isOutputType(type))
      return <IOOutputView outputId={id!} outputType={type} />;
    else return undefined;
  }

  function UpdateAccordion() {
    return (categories[selectedCategory]?.name ?? "Inputs") === "Inputs"
      ? inputs
      : outputs;
  }

  return (
    <BaseModal
      size={handleSelectChange() ? "large" : "small"}
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
          <div
            className={cn(
              "mr-6 flex h-full w-2/6 flex-col justify-start overflow-auto scrollbar-hide",
              handleSelectChange() ? "w-2/6" : "w-full"
            )}
          >
            <div className="flex w-full items-center justify-between py-2">
              <div className="flex items-start gap-4">
                {categories.map((category, index) => {
                  return (
                    //hide chat button if chat is alredy on the view
                    <Button
                      onClick={() => setSelectedCategory(index)}
                      variant={
                        index === selectedCategory ? "primary" : "secondary"
                      }
                      key={index}
                    >
                      <IconComponent
                        name={category.icon}
                        className=" file-component-variable"
                      />
                      <span className="file-component-variables-span text-md">
                        {category.name}
                      </span>
                    </Button>
                  );
                })}
              </div>
              {(outputs.map((output) => output.type).includes("ChatOutput") ||
                inputs.map((output) => output.type).includes("chatInput")) &&
                selectedView.type !== "ChatOutput" && (
                  <Button
                    onClick={() => setSelectedView({ type: "ChatOutput" })}
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
              {categories[selectedCategory].name === "Inputs" && (
                <>
                  <IconComponent name={"FormInput"} />
                  Text Inputs
                </>
              )}
              {categories[selectedCategory].name === "Outputs" && (
                <>
                  <IconComponent name={"ChevronRightSquare"} />
                  Prompt Outputs
                </>
              )}
            </div>
            {UpdateAccordion()
              .filter(
                (input) =>
                  input.type !== "ChatInput" && input.type !== "ChatOutput"
              )
              .map((input, index) => {
                const node: NodeType = nodes.find(
                  (node) => node.id === input.id
                )!;
                return (
                  <div className="file-component-accordion-div" key={index}>
                    <AccordionComponent
                      trigger={
                        <div className="file-component-badge-div">
                          <Badge variant="gray" size="md">
                            {input.id}
                          </Badge>
                          <div
                            className="-mb-1 pr-4"
                            onClick={(event) => {
                              event.stopPropagation();
                              setSelectedView({
                                type: input.type,
                                id: input.id,
                              });
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
                        {node &&
                          (categories[selectedCategory].name === "Inputs" ? (
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
                    </AccordionComponent>
                  </div>
                );
              })}
          </div>
          {handleSelectChange() && handleSelectChange()}
        </div>
      </BaseModal.Content>
    </BaseModal>
  );
}
