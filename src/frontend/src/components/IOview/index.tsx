import { cloneDeep } from "lodash";
import { ReactNode, useState } from "react";
import useFlowStore from "../../stores/flowStore";
import { NodeType } from "../../types/flow";
import { extractTypeFromLongId } from "../../utils/utils";
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
  const options = inputIds.concat(outputIds);
  //TODO: show output options for view
  const [selectedView, setSelectedView] = useState<ReactNode>(
    handleSelectChange(options[0])
  );
  // if (outputTypes.includes("ChatOutput")) {
  //   return <NewChatView />;
  // }
  function handleSelectChange(selected: string) {
    const type = extractTypeFromLongId(selected);
    return <NewChatView />;
    switch (type) {
      case "ChatOutput":
        return <NewChatView />;
        break;
    }
  }
  console.log(inputs);
  return (
    <div className="form-modal-iv-box">
      <div className="mr-6 flex h-full w-2/6 flex-col justify-start overflow-auto scrollbar-hide">
        <div className="file-component-arrangement">
          <IconComponent name="Variable" className=" file-component-variable" />
          <span className="file-component-variables-span text-md">Inputs</span>
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
      {selectedView}
    </div>
  );
}
