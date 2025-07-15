import { InputOutput } from "@/constants/enums";
import { cn } from "@/utils/utils";
import IconComponent from "../../../components/common/genericIconComponent";
import type { SelectedViewFieldProps } from "../types/selected-view-field";
import IOFieldView from "./IOFieldView/io-field-view";
import SessionView from "./session-view";

export const SelectedViewField = ({
  selectedViewField,
  setSelectedViewField,
  haveChat,
  inputs,
  outputs,
  sessions,
  currentFlowId,
  nodes,
}: SelectedViewFieldProps) => {
  return (
    <>
      <div
        className={cn(
          "flex h-full w-full flex-col items-start gap-4 p-4",
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
            nodes.find((node) => node.id === selectedViewField?.id)?.data.node
              .display_name
          }
        </div>
        <div className="h-full w-full">
          {inputs.some((input) => input.id === selectedViewField?.id) && (
            <IOFieldView
              type={InputOutput.INPUT}
              left={false}
              fieldType={selectedViewField?.type!}
              fieldId={selectedViewField?.id!}
            />
          )}
          {outputs.some((output) => output.id === selectedViewField?.id) && (
            <IOFieldView
              type={InputOutput.OUTPUT}
              left={false}
              fieldType={selectedViewField?.type!}
              fieldId={selectedViewField?.id!}
            />
          )}
          {sessions.some((session) => session === selectedViewField?.id) && (
            <SessionView session={selectedViewField?.id} id={currentFlowId} />
          )}
        </div>
      </div>
    </>
  );
};
