import {
  useGetGlobalVariables,
  usePostGlobalVariables,
} from "@/controllers/API/queries/variables";
import getUnavailableFields from "@/stores/globalVariablesStore/utils/get-unavailable-fields";
import { useEffect, useState } from "react";
import BaseModal from "../../modals/baseModal";
import useAlertStore from "../../stores/alertStore";
import { useTypesStore } from "../../stores/typesStore";
import { ResponseErrorDetailAPI } from "../../types/api";
import ForwardedIconComponent from "../genericIconComponent";
import InputComponent from "../inputComponent";
import { Input } from "../ui/input";
import { Label } from "../ui/label";
import { Textarea } from "../ui/textarea";
import sortByName from "./utils/sort-by-name";

//TODO IMPLEMENT FORM LOGIC

export default function AddNewVariableButton({
  children,
  asChild,
}: {
  children: JSX.Element;
  asChild?: boolean;
}): JSX.Element {
  const [key, setKey] = useState("");
  const [value, setValue] = useState("");
  const [type, setType] = useState("Generic");
  const [fields, setFields] = useState<string[]>([]);
  const [open, setOpen] = useState(false);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const componentFields = useTypesStore((state) => state.ComponentFields);
  const { mutate: mutateAddGlobalVariable } = usePostGlobalVariables();
  const { data: globalVariables } = useGetGlobalVariables();
  const [availableFields, setAvailableFields] = useState<string[]>([]);

  useEffect(() => {
    if (globalVariables && componentFields.size > 0) {
      const unavailableFields = getUnavailableFields(globalVariables);
      const fields = Array.from(componentFields).filter(
        (field) => !unavailableFields.hasOwnProperty(field),
      );

      setAvailableFields(sortByName(fields));
    }
  }, [globalVariables, componentFields]);

  const setSuccessData = useAlertStore((state) => state.setSuccessData);

  function handleSaveVariable() {
    let data: {
      name: string;
      value: string;
      type?: string;
      default_fields?: string[];
    } = {
      name: key,
      type,
      value,
      default_fields: fields,
    };

    mutateAddGlobalVariable(data, {
      onSuccess: (res) => {
        const { name } = res;
        setKey("");
        setValue("");
        setType("");
        setFields([]);
        setOpen(false);

        setSuccessData({
          title: `Variable ${name} created successfully`,
        });
      },
      onError: (error) => {
        let responseError = error as ResponseErrorDetailAPI;
        setErrorData({
          title: "Error creating variable",
          list: [
            responseError?.response?.data?.detail ??
              "An unexpected error occurred while adding a new variable. Please try again.",
          ],
        });
      },
    });
  }

  return (
    <BaseModal
      open={open}
      setOpen={setOpen}
      size="x-small"
      onSubmit={handleSaveVariable}
    >
      <BaseModal.Header
        description={
          "This variable will be encrypted and will be available for you to use in any of your projects."
        }
      >
        <span className="pr-2"> Create Variable </span>
        <ForwardedIconComponent
          name="Globe"
          className="h-6 w-6 pl-1 text-primary"
          aria-hidden="true"
        />
      </BaseModal.Header>
      <BaseModal.Trigger asChild={asChild}>{children}</BaseModal.Trigger>
      <BaseModal.Content>
        <div className="flex h-full w-full flex-col gap-4 align-middle">
          <Label>Variable Name</Label>
          <Input
            value={key}
            onChange={(e) => {
              setKey(e.target.value);
            }}
            placeholder="Insert a name for the variable..."
          ></Input>
          <Label>Type (optional)</Label>
          <InputComponent
            setSelectedOption={(e) => {
              setType(e);
            }}
            selectedOption={type}
            password={false}
            options={["Generic", "Credential"]}
            placeholder="Choose a type for the variable..."
            id={"type-global-variables"}
          ></InputComponent>
          <Label>Value</Label>
          {type === "Credential" ? (
            <InputComponent
              password
              value={value}
              onChange={(e) => {
                setValue(e);
              }}
              placeholder="Insert a value for the variable..."
            />
          ) : (
            <Textarea
              value={value}
              onChange={(e) => {
                setValue(e.target.value);
              }}
              placeholder="Insert a value for the variable..."
              className="w-full resize-none custom-scroll"
            />
          )}

          <Label>Apply To Fields (optional)</Label>
          <InputComponent
            setSelectedOptions={(value) => setFields(value)}
            selectedOptions={fields}
            options={availableFields}
            password={false}
            placeholder="Choose a field for the variable..."
            id={"apply-to-fields"}
          ></InputComponent>
        </div>
      </BaseModal.Content>
      <BaseModal.Footer
        submit={{ label: "Save Variable", dataTestId: "save-variable-btn" }}
      />
    </BaseModal>
  );
}
