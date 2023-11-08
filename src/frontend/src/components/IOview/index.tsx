import { ReactNode, useContext, useState } from "react";
import { flowManagerContext } from "../../contexts/flowManagerContext";
import NewChatView from "../newChatView";
import TextInputComponent from "../textInputComponent";
import TextOutputComponent from "../textOutputComponent";
import { extractTypeFromLongId, removeCountFromString } from "../../utils/utils";
import AccordionComponent from "../AccordionComponent";
import { Badge } from "../ui/badge";
import ShadTooltip from "../ShadTooltipComponent";

export default function IOView(): JSX.Element {
  const { flowPool, inputIds, outputIds, inputTypes, outputTypes } =
    useContext(flowManagerContext);
  const options = inputIds.concat(outputIds);
  const [selectedView, setSelectedView] = useState<ReactNode>(handleSelectChange(options[0]));
  if (outputTypes.includes("ChatOutput")) {
    return <NewChatView />;
  }
  function handleSelectChange(selected: string) {
    const type = extractTypeFromLongId(selected);
    switch (type) {
      case "ChatOutput":
        return <NewChatView />;
        break;
    }
  }


  return (
    <div className="flex-max-width mt-2 h-[80vh]">
      <div className="mr-6 flex h-full w-2/6 flex-col justify-start overflow-clip">
        <div className="w-full h-4/6 resize-y">
          <AccordionComponent trigger={
            <div className="file-component-badge-div">
              <Badge variant="gray" size="md">
                Outputs
              </Badge>
            </div>
          }>
            <div className="flex flex-col overflow-auto custom-scroll">
              {outputIds.map((id) => {
                return (
                  <ShadTooltip content={id}>
                    <div>
                      {extractTypeFromLongId(id)}
                    </div>
                  </ShadTooltip>
                )
              })}
            </div>
          </AccordionComponent>
        </div>
        <div className="w-full h-4/6 resize-y">
          <AccordionComponent trigger={
            <div className="file-component-badge-div">
              <Badge variant="gray" size="md">
                Inputs
              </Badge>
            </div>
          }>
            <div className="flex flex-col overflow-auto custom-scroll">
              {inputIds.map((id) => {
                return (
                  <ShadTooltip content={id}>
                    <div>
                      {extractTypeFromLongId(id)}
                    </div>
                  </ShadTooltip>
                )
              })}
            </div>
          </AccordionComponent>
        </div>
        {selectedView}
      </div>
    </div>
  );
}
