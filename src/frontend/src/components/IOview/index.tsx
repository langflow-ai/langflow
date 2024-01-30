import { cloneDeep } from "lodash";
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
  //TODO: show output options for view
  const [selectedView, setSelectedView] = useState<string>("Chat");

  function getCategories() {
    const categories: string[] = [];
    if (inputs.length > 0) categories.push("Inputs");
    if (outputs.filter((output) => output.type !== "ChatOutput").length > 0)
      categories.push("Outputs");
    if (outputs.map((output) => output.type).includes("ChatOutput"))
      categories.push("Chat");
    return categories;
  }

  function handleSelectChange(type?: string): ReactNode {
    if (selectedCategory === "Chat") return <NewChatView />;
    switch (type) {
      case "Chat":
        return <NewChatView />;
        break;
      // case "TextInput":
      //   break;
      default:
        //create empty view output screen
        return <div>no view selected</div>;
    }
  }
  return (
    <div className="form-modal-iv-box">
      <div className="mr-6 flex h-full w-2/6 flex-col justify-start overflow-auto scrollbar-hide">
        <div className="flex items-start gap-4 py-2">
          {categories.map((category, index) => {
            return (
              //hide chat button if chat is alredy on the view
              !(selectedView === category && category === "Chat") && (
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
              )
            );
          })}
        </div>
        {inputs
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
                        className="-mb-1"
                        onClick={(event) => {
                          event.stopPropagation();
                        }}
                      ></div>
                    </div>
                  }
                  key={index}
                  keyValue={input.id}
                >
                  <div className="file-component-tab-column">
                    {node && (
                      <IOInputField
                        field={node.data.node!.template["value"]}
                        inputType={input.type}
                        updateValue={(e) => {
                          e.target.value;
                          if (node) {
                            let newNode = cloneDeep(node);
                            newNode.data.node!.template["value"].value =
                              e.target.value;
                            setNode(node.id, newNode);
                          }
                        }}
                      />
                    )}
                  </div>
                </AccordionComponent>
              </div>
            );
          })}
      </div>
      {handleSelectChange(selectedView)}
    </div>
  );
}
