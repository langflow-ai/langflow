import { useEffect, useState } from "react";
import InputComponent from "../../../components/inputComponent";
import {
  FormControl,
  FormField,
  FormItem,
  FormMessage,
} from "../../../components/ui/form";
import { Input } from "../../../components/ui/input";
import { Label } from "../../../components/ui/label";
import { Textarea } from "../../../components/ui/textarea";
import useFlowsManagerStore from "../../../stores/flowsManagerStore";

type FolderFormsProps = {
  control: any;
  setValue: any;
  folderToEdit: any;
};

export const FolderForms = ({
  control,
  setValue,
  folderToEdit,
}: FolderFormsProps): JSX.Element => {
  const flows = useFlowsManagerStore((state) => state.flows);
  const [selectedComponents, setSelectedComponents] = useState<string[]>([]);
  const [selectedFlows, setSelectedFlows] = useState<string[]>([]);

  const componentsList = flows
    .filter((flow) => flow.is_component && flow.folder_id !== null)
    .map((flow) => ({ id: flow.id, name: flow.name }));

  const flowsList = flows
    .filter((flow) => !flow.is_component && flow.folder_id !== null)
    .map((flow) => ({ id: flow.id, name: flow.name }));

  useEffect(() => {
    setValue("components", selectedComponents);
    setValue("flows", selectedFlows);
  }, [selectedComponents, selectedFlows]);

  useEffect(() => {
    if (folderToEdit) {
      setValue("name", folderToEdit.name);
      setValue("description", folderToEdit.description);
      return;
    }
    setValue("name", "");
    setValue("description", "");
    setSelectedComponents([]);
    setSelectedFlows([]);
  }, [folderToEdit]);

  return (
    <>
      <div className="flex h-full w-full flex-col gap-4 align-middle">
        <Label>Folder Name</Label>

        <FormField
          control={control}
          name="name"
          render={({ field }) => (
            <FormItem>
              <FormControl>
                <Input
                  value={field.value}
                  onChange={field.onChange}
                  placeholder="Insert a name for the folder..."
                ></Input>
              </FormControl>

              <FormMessage />
            </FormItem>
          )}
        />

        <Label>Description (optional) </Label>

        <FormField
          control={control}
          name="description"
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

        <Label>Add Flows</Label>

        <FormField
          control={control}
          name="flows"
          render={() => (
            <FormControl>
              <InputComponent
                isObjectOption
                password={false}
                objectOptions={flowsList}
                placeholder="Choose a flow to add..."
                id="input-flow"
                setSelectedOptions={(value: any) => setSelectedFlows(value)}
                selectedOptions={selectedFlows}
              ></InputComponent>
            </FormControl>
          )}
        />

        <Label>Add Components</Label>
        <FormField
          control={control}
          name="components"
          render={() => (
            <FormControl>
              <InputComponent
                isObjectOption
                password={false}
                objectOptions={componentsList}
                placeholder="Choose a component to add..."
                id="input-component"
                setSelectedOptions={(value) => setSelectedComponents(value)}
                selectedOptions={selectedComponents}
              ></InputComponent>
            </FormControl>
          )}
        />
      </div>
    </>
  );
};

export default FolderForms;
