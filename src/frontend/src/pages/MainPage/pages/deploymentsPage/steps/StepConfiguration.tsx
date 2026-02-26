import { type Dispatch, type SetStateAction } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import GlobalVariableModal from "@/components/core/GlobalVariableModal/GlobalVariableModal";
import InputComponent from "@/components/core/parameterRenderComponent/components/inputComponent";
import { CommandItem } from "@/components/ui/command";
import { Input } from "@/components/ui/input";
import { useGetGlobalVariables } from "@/controllers/API/queries/variables";
import { cn } from "@/utils/utils";
import type { EnvVar } from "../constants";

type StepConfigurationProps = {
  envVars: EnvVar[];
  setEnvVars: Dispatch<SetStateAction<EnvVar[]>>;
  detectedVarCount: number;
};

export const StepConfiguration = ({
  envVars,
  setEnvVars,
  detectedVarCount,
}: StepConfigurationProps) => {
  const { data: globalVariables } = useGetGlobalVariables();
  const variableOptions = (globalVariables ?? []).map((v) => v.name);

  const handleSelectOption = (index: number, selected: string) => {
    setEnvVars((prev) =>
      prev.map((x, j) =>
        j === index
          ? {
              ...x,
              key:
                selected !== "" &&
                (x.key.trim() === "" || (x.globalVar && x.key === x.value))
                  ? selected
                  : x.key,
              value: selected,
              globalVar: selected !== "",
            }
          : x,
      ),
    );
  };

  const handleValueChange = (index: number, text: string) => {
    setEnvVars((prev) =>
      prev.map((x, j) =>
        j === index ? { ...x, value: text, globalVar: false } : x,
      ),
    );
  };

  const addVariableButton = (
    <GlobalVariableModal>
      <CommandItem value="doNotFilter-addNewVariable">
        <ForwardedIconComponent
          name="Plus"
          className={cn("mr-2 h-4 w-4 text-primary")}
          aria-hidden="true"
        />
        <span>Add New Variable</span>
      </CommandItem>
    </GlobalVariableModal>
  );

  return (
    <div className="flex h-full flex-col gap-4 overflow-hidden">
      <div>
        <h3 className="text-base font-semibold">Deployment Configuration</h3>
        <p className="mt-1 text-sm text-muted-foreground">
          Configure the environment variables for this deployment.
        </p>
      </div>

      <div className="flex min-h-0 flex-1 flex-col gap-1.5">
        <label className="text-sm font-medium">
          Environment Variables <span className="text-destructive">*</span>
        </label>
        {detectedVarCount > 0 && (
          <p className="text-xs text-muted-foreground">
            {detectedVarCount} variable{detectedVarCount > 1 ? "s" : ""}{" "}
            auto-detected from your selected checkpoints.
          </p>
        )}
        <div className="flex h-full min-h-0 flex-col rounded-lg bg-muted/40">
          <div className="min-h-0 flex-1 overflow-y-auto">
            {envVars.length === 0 ? (
              <p className="flex h-full min-h-[80px] items-center justify-center text-sm text-muted-foreground">
                No variables yet. Click &quot;Add Variable&quot; to get started.
              </p>
            ) : (
              <div className="flex flex-col">
                {envVars.map((v, i) => (
                  <div
                    key={i}
                    className="grid grid-cols-[2fr_3fr_auto] items-center gap-2 p-2"
                  >
                    <Input
                      placeholder="KEY"
                      value={v.key}
                      onChange={(e) =>
                        setEnvVars((prev) =>
                          prev.map((x, j) =>
                            j === i ? { ...x, key: e.target.value } : x,
                          ),
                        )
                      }
                      className="min-w-0"
                    />
                    <div className="min-w-0">
                      <InputComponent
                        nodeStyle
                        password
                        popoverWidth="17.5rem"
                        placeholder="Type something..."
                        id={`env-val-${i}`}
                        value={v.value}
                        options={variableOptions}
                        optionsPlaceholder="Global Variables"
                        optionsIcon="Globe"
                        optionsButton={addVariableButton}
                        selectedOption={v.globalVar ? v.value : ""}
                        setSelectedOption={(sel) => handleSelectOption(i, sel)}
                        onChange={(text) => handleValueChange(i, text)}
                      />
                    </div>
                    <button
                      onClick={() =>
                        setEnvVars((prev) => prev.filter((_, j) => j !== i))
                      }
                      className="text-muted-foreground hover:text-destructive"
                    >
                      <ForwardedIconComponent
                        name="Trash2"
                        className="h-4 w-4"
                      />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
          <div className="sticky bottom-0 border-t border-border bg-background/95 px-3 py-2 backdrop-blur supports-[backdrop-filter]:bg-background/80">
            <button
              onClick={() =>
                setEnvVars((prev) => [...prev, { key: "", value: "" }])
              }
              className="group flex w-full items-center justify-start gap-2 rounded-md border border-border bg-background px-3 py-2 text-sm font-medium text-foreground shadow-sm transition-colors hover:border-primary/50 hover:bg-primary/10"
            >
              <span className="flex h-5 w-5 items-center justify-center rounded-sm bg-muted text-muted-foreground transition-colors group-hover:bg-primary/20 group-hover:text-primary">
                <ForwardedIconComponent name="Plus" className="h-3.5 w-3.5" />
              </span>
              Add Variable
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
