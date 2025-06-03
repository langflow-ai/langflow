import {
  useGetGlobalVariables,
  usePatchGlobalVariables,
  usePostGlobalVariables,
} from "@/controllers/API/queries/variables";
import { GlobalVariable } from "@/types/global_variables";
import { useState } from "react";

import { ForwardedIconComponent } from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs-button";
import { Textarea } from "@/components/ui/textarea";
import { useGetTypes } from "@/controllers/API/queries/flows/use-get-types";
import { CustomLink } from "@/customization/components/custom-link";
import BaseModal from "@/modals/baseModal";
import useAlertStore from "@/stores/alertStore";
import { useTypesStore } from "@/stores/typesStore";
import { ResponseErrorDetailAPI } from "@/types/api";

//TODO IMPLEMENT FORM LOGIC

export default function AddMcpServerModal({
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
  useGetTypes({ checkCache: true, enabled: !!globalVariables });

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
    if (!initialData || !initialData.id) {
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
      className="!p-4"
    >
      <BaseModal.Trigger disable={disabled} asChild={asChild}>
        {children}
      </BaseModal.Trigger>
      <BaseModal.Content className="flex flex-col gap-4">
        <div className="flex flex-col gap-3 tracking-normal">
          <div className="flex items-center gap-2 text-sm font-medium">
            <ForwardedIconComponent
              name="Mcp"
              className="h-4 w-4 text-primary"
              aria-hidden="true"
            />
            {initialData ? "Update MCP Server" : "Add MCP Server"}
          </div>
          <span className="text-mmd font-normal text-muted-foreground">
            Save MCP Servers. Manage added connections in{" "}
            <CustomLink className="underline" to="/settings/mcp-servers">
              settings
            </CustomLink>
            .
          </span>
        </div>
        <div className="flex h-full w-full flex-col gap-4">
          <div className="">
            <Tabs
              defaultValue={type}
              onValueChange={setType}
              className="w-full"
            >
              <TabsList className="grid w-full grid-cols-3">
                <TabsTrigger
                  disabled={!!initialData?.type}
                  data-testid="json-tab"
                  value="JSON"
                >
                  JSON
                </TabsTrigger>
                <TabsTrigger
                  disabled={!!initialData?.type}
                  data-testid="stdio-tab"
                  value="STDIO"
                >
                  STDIO
                </TabsTrigger>
                <TabsTrigger
                  disabled={!!initialData?.type}
                  data-testid="json-tab"
                  value="SSE"
                >
                  SSE
                </TabsTrigger>
              </TabsList>
            </Tabs>
          </div>

          <div className="space-y-2" id="global-variable-modal-inputs">
            <Label className="!text-mmd">Paste in JSON config</Label>
            <Textarea
              value={value}
              onChange={(e) => setValue(e.target.value)}
              className="min-h-40 font-mono text-mmd"
              placeholder="Paste in JSON config to add server"
            />
          </div>
        </div>
        <div className="flex justify-end gap-2">
          <Button variant="outline" size="sm" onClick={() => setOpen(false)}>
            <span className="text-mmd font-normal">Cancel</span>
          </Button>
          <Button size="sm" onClick={submitForm}>
            <span className="text-mmd">Add Server</span>
          </Button>
        </div>
      </BaseModal.Content>
    </BaseModal>
  );
}
