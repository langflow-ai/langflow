import { ReactNode, useState } from "react";
import useFlowStore from "../../stores/flowStore";
import { NodeType } from "../../types/flow";
import { classNames } from "../../utils/utils";
import AccordionComponent from "../AccordionComponent";
import IOInputField from "../IOInputField";
import IconComponent from "../genericIconComponent";
import NewChatView from "../newChatView";
import { Badge } from "../ui/badge";

export default function IOView(): JSX.Element {
  const inputs = useFlowStore((state) => state.inputs);
  const outputs = useFlowStore((state) => state.outputs);
  const inputIds = inputs.map((obj) => obj.id);
  const outputIds = outputs.map((obj) => obj.id);
  const nodes = useFlowStore((state) => state.nodes);
  const setNode = useFlowStore((state) => state.setNode);
  const categories = getCategories();
  const [selectedCategory, setSelectedCategory] = useState<string>(
    categories[0]
  );
  const [showChat, setShowChat] = useState<boolean>(false);
  //TODO: show output options for view
  const [selectedView, setSelectedView] = useState<{
    type: string;
    id?: string;
  }>(handleInitialView());

  function handleInitialView() {
    if (outputs.map((output) => output.type).includes("ChatOutput")) {
      return { type: "ChatOutput" };
    }
    return { type: "" };
  }

  function getCategories() {
    const categories: string[] = [];
    if (inputs.length > 0) categories.push("Inputs");
    if (outputs.filter((output) => output.type !== "ChatOutput").length > 0)
      categories.push("Outputs");
    return categories;
  }

  function handleSelectChange(): ReactNode {
    const { type, id } = selectedView;
    switch (type) {
      case "ChatOutput":
        return <NewChatView />;
        break;
      case "TextInput":
        return <IOInputField inputId={id!} inputType={type} />;
      default:
        //create empty view output screen
        return <div>no view selected</div>;
    }
  }

  function UpdateAccordion() {
    return selectedCategory === "Inputs" ? inputs : outputs;
  }

  return (
    <div className="form-modal-iv-box">
      <div className="mr-6 flex h-full w-2/6 flex-col justify-start overflow-auto scrollbar-hide">
        <div className="flex items-start gap-4 py-2">
          {categories.map((category, index) => {
            return (
              //hide chat button if chat is alredy on the view
              <button
                onClick={() => setSelectedCategory(category)}
                className={classNames(
                  "cursor flex items-center rounded-md rounded-b-none px-1",
                  category == selectedCategory
                    ? "border border-b-0 border-muted-foreground"
                    : "hover:bg-muted-foreground"
                )}
                key={index}
              >
                <IconComponent
                  name="Variable"
                  className=" file-component-variable"
                />
                <span className="file-component-variables-span text-md">
                  {category}
                </span>
              </button>
            );
          })}
          {selectedView.type !== "ChatOutput" && (
            <button
              onClick={() => setSelectedView({ type: "ChatOutput" })}
              className={
                "cursor flex items-center rounded-md rounded-b-none px-1 hover:bg-muted-foreground"
              }
              key={"chat"}
            >
              <IconComponent
                name="Variable"
                className=" file-component-variable"
              />
              <span className="file-component-variables-span text-md">
                Chat
              </span>
            </button>
          )}
        </div>
        {UpdateAccordion()
          .filter((input) => input.type !== "ChatInput")
          .map((input, index) => {
            const node: NodeType = nodes.find((node) => node.id === input.id)!;
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
                          setSelectedView({ type: input.type, id: input.id });
                        }}
                      >
                        <IconComponent
                          className="h-4 w-4"
                          name="ScreenShare"
                        ></IconComponent>
                      </div>
                    </div>
                  }
                  key={index}
                  keyValue={input.id}
                >
                  <div className="file-component-tab-column">
                    {node && (
                      <IOInputField inputType={input.type} inputId={input.id} />
                    )}
                  </div>
                </AccordionComponent>
              </div>
            );
          })}
      </div>
      {handleSelectChange()}
    </div>
  );
}
