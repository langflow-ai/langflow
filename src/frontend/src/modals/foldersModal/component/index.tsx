import { useEffect, useState } from "react";
import { Control, UseFormSetValue } from "react-hook-form";
import { FolderFormsType } from "..";
import InputComponent from "../../../components/inputComponent";
import { FormControl, FormField } from "../../../components/ui/form";
import { Input } from "../../../components/ui/input";
import { Label } from "../../../components/ui/label";
import { Textarea } from "../../../components/ui/textarea";
import useFlowsManagerStore from "../../../stores/flowsManagerStore";

type FolderFormsProps = {
  control: Control<FolderFormsType, any>;
  setValue: UseFormSetValue<FolderFormsType>;
};

export const FolderForms = ({
  control,
  setValue,
}: FolderFormsProps): JSX.Element => {
  const flows = useFlowsManagerStore((state) => state.flows);
  const [selectedComponents, setSelectedComponents] = useState<string[]>([]);
  const [selectedFlows, setSelectedFlows] = useState<string[]>([]);

  const componentsList = flows
    .filter((flow) => flow.is_component)
    .map((flow) => ({ id: flow.id, name: flow.name }));

  const flowsList = flows
    .filter((flow) => !flow.is_component)
    .map((flow) => ({ id: flow.id, name: flow.name }));

  useEffect(() => {
    setValue("components", selectedComponents);
    setValue("flows", selectedFlows);
  }, [selectedComponents, selectedFlows]);

  return (
    <>
      <div className="flex h-full w-full flex-col gap-4 align-middle">
        <Label>Folder Name</Label>

        <FormField
          control={control}
          name="folderName"
          defaultValue={""}
          render={({ field }) => (
            <FormControl>
              <Input
                value={field.value}
                onChange={field.onChange}
                placeholder="Insert a name for the folder..."
              ></Input>
            </FormControl>
          )}
        />

        <Label>Description (optional) </Label>

        <FormField
          control={control}
          defaultValue={""}
          name="folderDescription"
          render={({ field }) => (
            <FormControl>
              <Textarea
                value={field.value}
                onChange={field.onChange}
                placeholder="Insert a description for the folder..."
              ></Textarea>
            </FormControl>
          )}
        />

        <Label>Add Components</Label>
        <FormField
          control={control}
          defaultValue={[]}
          name="components"
          render={() => (
            <FormControl>
              <InputComponent
                isObjectOption
                password={false}
                objectOptions={componentsList}
                placeholder="Choose a type for the variable..."
                id={"type-global-variables"}
                setSelectedOptions={(value) => setSelectedComponents(value)}
                selectedOptions={selectedComponents}
              ></InputComponent>
            </FormControl>
          )}
        />

        <Label>Add Flows</Label>

        <FormField
          control={control}
          defaultValue={[]}
          name="flows"
          render={() => (
            <FormControl>
              <InputComponent
                isObjectOption
                password={false}
                objectOptions={flowsList}
                placeholder="Choose a type for the variable..."
                id={"type-global-variables"}
                setSelectedOptions={(value: any) => setSelectedFlows(value)}
                selectedOptions={selectedFlows}
              ></InputComponent>
            </FormControl>
          )}
        />
      </div>
    </>
  );
};

export default FolderForms;
