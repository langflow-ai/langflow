import type { AgGridReact } from "ag-grid-react";
import { cloneDeep } from "lodash";
import { type ForwardedRef, forwardRef, useEffect, useState } from "react";
import type { handleOnNewValueType } from "@/CustomNodes/hooks/use-handle-new-value";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { SidebarProvider } from "@/components/ui/sidebar";
import type { AuthSettingsType } from "@/types/mcp";
import BaseModal from "../baseModal";
import ToolsTable from "./components/toolsTable";

interface ToolsModalProps {
  open: boolean;
  setOpen: (open: boolean) => void;
  description: string;
  rows: {
    name: string;
    tags: string[];
    description: string;
    status: boolean;
  }[];
  placeholder: string;
  handleOnNewValue: handleOnNewValueType;
  title: string;
  icon?: string;
  isAction?: boolean;
  authSettings?: AuthSettingsType;
}

const ToolsModal = forwardRef<AgGridReact, ToolsModalProps>(
  (
    {
      description,
      rows,
      placeholder,
      handleOnNewValue,
      title,
      icon,
      open,
      isAction = false,
      setOpen,
      authSettings,
    }: ToolsModalProps,
    ref: ForwardedRef<AgGridReact>,
  ) => {
    const handleSetOpen = (newOpen: boolean) => {
      if (setOpen) {
        setOpen(newOpen);
      }
    };

    const [data, setData] = useState<any[]>(cloneDeep(rows));
    const [authType, setAuthType] = useState<string>(
      authSettings?.auth_type || "none",
    );
    const [authFields, setAuthFields] = useState<{
      apiKey?: string;
      username?: string;
      password?: string;
      bearerToken?: string;
    }>({
      apiKey: authSettings?.api_key || "",
      username: authSettings?.username || "",
      password: authSettings?.password || "",
      bearerToken: authSettings?.bearer_token || "",
    });

    useEffect(() => {
      if (placeholder === "Loading actions...") {
        handleOnNewValue({
          value: [],
        });
      }
    }, [placeholder]);

    // Update auth state when authSettings prop changes
    useEffect(() => {
      if (authSettings) {
        setAuthType(authSettings.auth_type || "none");
        setAuthFields({
          apiKey: authSettings.api_key || "",
          username: authSettings.username || "",
          password: authSettings.password || "",
          bearerToken: authSettings.bearer_token || "",
        });
      }
    }, [authSettings]);

    const handleAuthTypeChange = (type: string) => {
      setAuthType(type);
      setAuthFields({});
    };

    const handleAuthFieldChange = (field: string, value: string) => {
      setAuthFields((prev) => ({
        ...prev,
        [field]: value,
      }));
    };

    return (
      <BaseModal
        open={open}
        size="templates"
        className="flex max-h-[50vh] gap-0 p-0"
        setOpen={(newOpen) => {
          handleSetOpen(newOpen);
        }}
      >
        <BaseModal.Header>
          <div className="flex w-full flex-row items-center border-b border-border px-4 py-3">
            {icon && (
              <ForwardedIconComponent name={icon} className="mr-2 h-6 w-6" />
            )}
            <div>{title}</div>
          </div>
        </BaseModal.Header>
        <BaseModal.Content overflowHidden className="flex flex-col p-0">
          <div className="flex flex-col w-full h-full">
            <div className="p-4 border-b border-border">
              <div className="space-y-4">
                <div>
                  <Label className="text-sm font-medium mb-3 block">
                    Authentication
                  </Label>
                  <div className="space-y-2">
                    {[
                      { id: "none", label: "None" },
                      { id: "apikey", label: "API Key" },
                      { id: "userpass", label: "Username & Password" },
                      { id: "bearer", label: "Bearer Token" },
                      { id: "iam", label: "IAM" },
                    ].map((option) => (
                      <div
                        key={option.id}
                        className="flex items-center space-x-2"
                      >
                        <input
                          type="radio"
                          id={option.id}
                          name="auth-type"
                          value={option.id}
                          checked={authType === option.id}
                          onChange={(e) => handleAuthTypeChange(e.target.value)}
                          className="h-4 w-4 text-primary focus:ring-primary focus:ring-2"
                        />
                        <Label
                          htmlFor={option.id}
                          className="text-sm font-normal cursor-pointer"
                        >
                          {option.label}
                        </Label>
                      </div>
                    ))}
                  </div>
                </div>

                {authType === "apikey" && (
                  <div className="space-y-2">
                    <Label htmlFor="api-key" className="text-sm font-medium">
                      API Key
                    </Label>
                    <Input
                      id="api-key"
                      type="password"
                      placeholder="Enter API key"
                      value={authFields.apiKey || ""}
                      onChange={(e) =>
                        handleAuthFieldChange("apiKey", e.target.value)
                      }
                    />
                  </div>
                )}

                {authType === "userpass" && (
                  <div className="space-y-4">
                    <div className="space-y-2">
                      <Label htmlFor="username" className="text-sm font-medium">
                        Username
                      </Label>
                      <Input
                        id="username"
                        type="text"
                        placeholder="Enter username"
                        value={authFields.username || ""}
                        onChange={(e) =>
                          handleAuthFieldChange("username", e.target.value)
                        }
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="password" className="text-sm font-medium">
                        Password
                      </Label>
                      <Input
                        id="password"
                        type="password"
                        placeholder="Enter password"
                        value={authFields.password || ""}
                        onChange={(e) =>
                          handleAuthFieldChange("password", e.target.value)
                        }
                      />
                    </div>
                  </div>
                )}

                {authType === "bearer" && (
                  <div className="space-y-2">
                    <Label
                      htmlFor="bearer-token"
                      className="text-sm font-medium"
                    >
                      Bearer Token
                    </Label>
                    <Input
                      id="bearer-token"
                      type="password"
                      placeholder="Enter bearer token"
                      value={authFields.bearerToken || ""}
                      onChange={(e) =>
                        handleAuthFieldChange("bearerToken", e.target.value)
                      }
                    />
                  </div>
                )}

                {authType === "iam" && (
                  <div className="text-sm text-muted-foreground">
                    IAM authentication will use your configured AWS credentials.
                  </div>
                )}
              </div>
            </div>
            <div className="flex h-full">
              <SidebarProvider width="20rem" defaultOpen={false}>
                <ToolsTable
                  rows={rows}
                  isAction={isAction}
                  placeholder={placeholder}
                  data={data}
                  setData={setData}
                  open={open}
                  handleOnNewValue={handleOnNewValue}
                  authType={authType}
                  authFields={authFields}
                />
              </SidebarProvider>
            </div>
          </div>
        </BaseModal.Content>
      </BaseModal>
    );
  },
);

export default ToolsModal;
