import { cloneDeep } from "lodash";
import { ReactNode, useState } from "react";
import useFlowStore from "../../stores/flowStore";
import { NodeType } from "../../types/flow";
import { extractTypeFromLongId } from "../../utils/utils";
import AccordionComponent from "../AccordionComponent";
import IconComponent from "../genericIconComponent";
import NewChatView from "../newChatView";
import { Badge } from "../ui/badge";
import { Textarea } from "../ui/textarea";
import IOInputField from "../IOInputField";

export default function IOView(): JSX.Element {
  const inputs = useFlowStore((state) => state.inputs);
  const outputs = useFlowStore((state) => state.outputs);
  const inputIds = inputs.map((obj) => obj.id);
  const outputIds = outputs.map((obj) => obj.id);
  const nodes = useFlowStore((state) => state.nodes);
  const setNode = useFlowStore((state) => state.setNode);
  const options = inputIds.concat(outputIds);
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
  console.log(inputs)
  return (
    <div className="form-modal-iv-box">
      <div className="mr-6 flex h-full w-2/6 flex-col justify-start overflow-auto scrollbar-hide">
        <div className="file-component-arrangement">
          <IconComponent name="Variable" className=" file-component-variable" />
          <span className="file-component-variables-span text-md">Inputs</span>
        </div>
        {inputIds
          .filter((input) => extractTypeFromLongId(input) !== "ChatInput")
          .map((inputId, index) => {
            const node: NodeType = nodes.find((node) => node.id === inputId)!;
            return (
              <div className="file-component-accordion-div" key={index}>
                <AccordionComponent
                  trigger={
                    <div className="file-component-badge-div">
                      <Badge variant="gray" size="md">
                        {inputId}
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
                  keyValue={inputId}
                >
                  {/* TODO: EXTEND AND IMPROVE VIEW MODE AND ADD OTHER TYPES OF VIEWS */}
                  <div className="file-component-tab-column">
                    <IOInputField
                      value={nodes.find((node) => node.id === inputId)?.data.node.template.value.value}
                      styleClasses="custom-scroll"
                      placeholder="Enter text..."
                      inputType={inputs.find((input) => input.id === inputId)?.type!}
                      onChange={(e) => {
                        e.target.value;
                        if (node) {
                            let newNode = cloneDeep(node);
                            newNode.data.node!.template["value"].value =
                            e.target.value;
                            setNode(node.id, newNode);
                        }
                        }}
                    />
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
