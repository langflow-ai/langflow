import { useEffect, useState } from "react";
import { ForwardedIconComponent } from "@/components/common/genericIconComponent";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs-button";
import { PROVIDER_VARIABLE_MAPPING } from "@/constants/providerConstants";
import { useGetTypes } from "@/controllers/API/queries/flows/use-get-types";
import {
  useGetGlobalVariables,
  usePatchGlobalVariables,
  usePostGlobalVariables,
} from "@/controllers/API/queries/variables";
import BaseModal from "@/modals/baseModal";
import useAlertStore from "@/stores/alertStore";
import getUnavailableFields from "@/stores/globalVariablesStore/utils/get-unavailable-fields";
import { useTypesStore } from "@/stores/typesStore";
import type { ResponseErrorDetailAPI } from "@/types/api";
import type { GlobalVariable, TAB_TYPES } from "@/types/global_variables";
import InputComponent from "../parameterRenderComponent/components/inputComponent";
import { assignTab } from "./utils/assign-tab";
import sortByName from "./utils/sort-by-name";

//TODO IMPLEMENT FORM LOGIC

export default function GlobalVariableModal({
  children,
  asChild,
  initialData,
  referenceField,
  open: myOpen,
  setOpen: mySetOpen,
  disabled = false,
}: {
  children?: JSX.Element;
  asChild?: boolean;
  initialData?: GlobalVariable;
  referenceField?: string;
  open?: boolean;
  setOpen?: (a: boolean | ((o?: boolean) => boolean)) => void;
  disabled?: boolean;
}): JSX.Element {
  const [key, setKey] = useState(initialData?.name ?? "");
  const [value, setValue] = useState(initialData?.value ?? "");
  const [type, setType] = useState<TAB_TYPES>(
    initialData?.type ?? "Credential",
  );
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
  useGetTypes({ checkCache: true, enabled: !!globalVariables });

  useEffect(() => {
    if (globalVariables && componentFields.size > 0) {
      const unavailableFields = getUnavailableFields(globalVariables);
      const fields = Array.from(componentFields).filter(
        (field) => !Object.hasOwn(unavailableFields, field.trim()),
      );
      setAvailableFields(
        sortByName(fields.concat(initialData?.default_fields ?? [])),
      );
      if (referenceField && fields.includes(referenceField)) {
        setFields([referenceField]);
      }
    } else {
      setAvailableFields(["System", "System Message", "System Prompt"]);
    }
  }, [globalVariables, componentFields, initialData]);

  const setSuccessData = useAlertStore((state) => state.setSuccessData);

  const handleOnValueCHange = (value: string) => {
    setType(assignTab(value));
  };

  function handleSaveVariable() {
    const data: {
      name: string;
      value: string;
      type?: TAB_TYPES;
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
        setType("Credential");
        setFields([]);
        setOpen(false);

        setSuccessData({
          title: `Variable ${name} ${
            initialData ? "updated" : "created"
          } successfully`,
        });
      },
      onError: (error) => {
        const responseError = error as ResponseErrorDetailAPI;
        setErrorData({
          title: `Error ${initialData ? "updating" : "creating"} variable`,
          list: [
            responseError?.response?.data?.detail ??
              `An unexpected error occurred while ${
                initialData ? "updating a new" : "creating"
              } variable. Please try again.`,
          ],
        });
      },
    });
  }

  function submitForm() {
    if (!initialData || !initialData.id) {
      handleSaveVariable();
    } else {
      // Check if this is a model provider variable based on the original variable name
      // The backend validates based on the existing variable name, not the new name
      const isModelProviderVariable = Object.values(
        PROVIDER_VARIABLE_MAPPING,
      ).includes(initialData.name);

      updateVariable(
        {
          id: initialData.id,
          name: key,
          value: value,
          default_fields: fields,
        },
        {
          onSuccess: (res) => {
            const { name } = res;
            setKey("");
            setValue("");
            setType("Credential");
            setFields([]);
            setOpen(false);

            setSuccessData({
              title: `Variable ${name} updated successfully`,
            });
          },
          onError: (error) => {
            const responseError = error as ResponseErrorDetailAPI;
            const errorMessage =
              responseError?.response?.data?.detail ??
              "An unexpected error occurred while updating the variable. Please try again.";

            setErrorData({
              title: isModelProviderVariable
                ? "Invalid API Key"
                : "Error updating variable",
              list: [errorMessage],
            });
          },
        },
      );
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
              onValueChange={handleOnValueCHange}
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

          <div className="space-y-2" id="global-variable-modal-inputs">
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
              popoverWidth="29rem"
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
          disabled: !key || !value,
        }}
      />
    </BaseModal>
  );
}
