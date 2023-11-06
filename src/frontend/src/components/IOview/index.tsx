import { useContext } from "react";
import { flowManagerContext } from "../../contexts/flowManagerContext";
import NewChatView from "../newChatView";
import TextInputComponent from "../textInputComponent";
import TextOutputComponent from "../textOutputComponent";

export default function IOView(): JSX.Element {
  const { flowPool, inputIds, outputIds, inputTypes, outputTypes } =
    useContext(flowManagerContext);

  if (inputTypes.includes("ChatInput") && outputTypes.includes("ChatOutput")) {
    return <NewChatView />;
  }

  return (
    <div className="flex w-full justify-around">
      <div className="flex flex-col gap-4">
        <strong>Inputs:</strong>
        {inputIds.map((inputType, index) => {
          let params = "";
          if (flowPool[inputType] && flowPool[inputType].length > 0)
            params = flowPool[inputType][flowPool[inputType].length - 1]
              .params as string;
          return (
            <div key={index}>
              <TextInputComponent
                text={params}
                emissor={inputType}
              ></TextInputComponent>
            </div>
          );
        })}
      </div>
      <div className="flex flex-col gap-4">
        <strong>Outputs:</strong>
        {outputIds.map((outputType, index) => {
          let text = "";
          if (flowPool[outputType] && flowPool[outputType].length > 0)
            text = flowPool[outputType][flowPool[outputType].length - 1].data
              .results?.result as string;
          return (
            <div key={index}>
              <TextOutputComponent
                text={text}
                emissor={outputType}
              ></TextOutputComponent>
            </div>
          );
        })}
      </div>
    </div>
  );
}
