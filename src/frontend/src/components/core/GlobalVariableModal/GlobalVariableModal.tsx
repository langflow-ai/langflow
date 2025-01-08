import {
  useGetGlobalVariables,
  usePatchGlobalVariables,
  usePostGlobalVariables,
} from "@/controllers/API/queries/variables";
import getUnavailableFields from "@/stores/globalVariablesStore/utils/get-unavailable-fields";
import { GlobalVariable } from "@/types/global_variables";
import { useEffect, useState } from "react";

import { ForwardedIconComponent } from "@/components/common/genericIconComponent";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs-button";
import BaseModal from "@/modals/baseModal";
import useAlertStore from "@/stores/alertStore";
import { useTypesStore } from "@/stores/typesStore";
import { ResponseErrorDetailAPI } from "@/types/api";
import InputComponent from "../parameterRenderComponent/components/inputComponent";
import sortByName from "./utils/sort-by-name";

//TODO IMPLEMENT FORM LOGIC

export default function GlobalVariableModal({
  children,
  asChild,
  initialData,
  open: myOpen,
  setOpen: mySetOpen,
  disabled = false,
}: {
  children?: JSX.Element;
  asChild?: boolean;
  initialData?: GlobalVariable;
  open?: boolean;
  setOpen?: (a: boolean | ((o?: boolean) => boolean)) => void;
  disabled?: boolean;
}): JSX.Element {
  const [key, setKey] = useState(initialData?.name ?? "");
  const [value, setValue] = useState(initialData?.value ?? "");
  const [type, setType] = useState(initialData?.type ?? "Credential");
  const [fields, setFields] = useState<string[]>(
    initialData?.default_fields ?? [],
  );
  const [open, setOpen] =
    mySetOpen !== undefined && myOpen !== undefined
      ? [myOpen, mySetOpen]
      : useState(false);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const componentFields = useTypesStore((state) => state.ComponentFields);
  const { mutate: mutateAddGlobalVariable } = usePostGlobalVariables();
  const { mutate: updateVariable } = usePatchGlobalVariables();
  const { data: globalVariables } = useGetGlobalVariables();
  const [availableFields, setAvailableFields] = useState<string[]>([]);

  useEffect(() => {
    if (globalVariables && componentFields.size > 0) {
      const unavailableFields = getUnavailableFields(globalVariables);
      const fields = Array.from(componentFields).filter(
        (field) => !unavailableFields.hasOwnProperty(field.trim()),
      );
      setAvailableFields(
        sortByName(fields.concat(initialData?.default_fields ?? [])),
      );
    }
  }, [globalVariables, componentFields, initialData]);

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
          title: `Variable ${name} ${initialData ? "updated" : "created"} successfully`,
        });
      },
      onError: (error) => {
        let responseError = error as ResponseErrorDetailAPI;
        setErrorData({
          title: `Error ${initialData ? "updating" : "creating"} variable`,
          list: [
            responseError?.response?.data?.detail ??
              `An unexpected error occurred while ${initialData ? "updating a new" : "creating"} variable. Please try again.`,
          ],
        });
      },
    });
  }

  function submitForm() {
    if (!initialData) {
      handleSaveVariable();
    } else {
      updateVariable({
        id: initialData.id,
        name: key,
        value: value,
        default_fields: fields,
      });
      setOpen(false);
    }
  }

  return (
    <BaseModal
      open={open}
      setOpen={setOpen}
      size="x-small"
      onSubmit={submitForm}
      disable={disabled}
    >
      <BaseModal.Header description="This variable will be available for use across your flows.">
        <ForwardedIconComponent
          name="Globe"
          className="h-6 w-6 pr-1 text-primary"
          aria-hidden="true"
        />
        {initialData ? "Update Variable" : "Create Variable"}
      </BaseModal.Header>
      <BaseModal.Trigger disable={disabled} asChild={asChild}>
        {children}
      </BaseModal.Trigger>
      <BaseModal.Content>
        <div className="flex h-full w-full flex-col gap-4">
          <div className="space-y-2">
            <Label>Type*</Label>
            <Tabs
              defaultValue={type}
              onValueChange={setType}
              className="w-full"
            >
              <TabsList className="grid w-full grid-cols-2">
                <TabsTrigger
                  disabled={!!initialData?.type}
                  data-testid="credential-tab"
                  value="Credential"
                >
                  Credential
                </TabsTrigger>
                <TabsTrigger
                  disabled={!!initialData?.type}
                  data-testid="generic-tab"
                  value="Generic"
                >
                  Generic
                </TabsTrigger>
              </TabsList>
            </Tabs>
          </div>

          <div className="space-y-2">
            <Label>Name*</Label>
            <Input
              value={key}
              onChange={(e) => setKey(e.target.value)}
              placeholder="Enter a name for the variable..."
            />
          </div>

          <div className="space-y-2">
            <Label>Value*</Label>
            {type === "Credential" ? (
              <InputComponent
                password
                value={value}
                onChange={(e) => setValue(e)}
                placeholder="Enter a value for the variable..."
                nodeStyle
              />
            ) : (
              <Input
                value={value}
                onChange={(e) => setValue(e.target.value)}
                placeholder="Enter a value for the variable..."
              />
            )}
          </div>

          <div className="space-y-2">
            <Label>Apply to fields</Label>
            <InputComponent
              setSelectedOptions={(value) => setFields(value)}
              selectedOptions={fields}
              options={availableFields}
              password={false}
              placeholder="Choose a field for the variable..."
              id="apply-to-fields"
              popoverWidth="520px"
              optionsPlaceholder="Fields"
            />
            <div className="text-xs text-muted-foreground">
              Selected fields will auto-apply the variable as a default value.
            </div>
          </div>
        </div>
      </BaseModal.Content>
      <BaseModal.Footer
        submit={{
          label: `${initialData ? "Update" : "Save"} Variable`,
          dataTestId: "save-variable-btn",
        }}
      />
    </BaseModal>
  );
}
