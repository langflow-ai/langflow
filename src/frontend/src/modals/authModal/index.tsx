import { useState, useEffect } from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import type { AuthSettingsType } from "@/types/mcp";
import BaseModal from "../baseModal";
import { Separator } from "@/components/ui/separator";
import ForwardedIconComponent from "@/components/common/genericIconComponent";

interface AuthModalProps {
  open: boolean;
  setOpen: (open: boolean) => void;
  authSettings?: AuthSettingsType;
  onSave: (authSettings: AuthSettingsType) => void;
}

const AuthModal = ({ open, setOpen, authSettings, onSave }: AuthModalProps) => {
  const [authType, setAuthType] = useState<string>(
    authSettings?.auth_type || "none"
  );
  const [authFields, setAuthFields] = useState<{
    apiKey?: string;
    iamEndpoint?: string;
    username?: string;
    password?: string;
    bearerToken?: string;
  }>({
    apiKey: authSettings?.api_key || "",
    iamEndpoint: authSettings?.iam_endpoint || "",
    username: authSettings?.username || "",
    password: authSettings?.password || "",
    bearerToken: authSettings?.bearer_token || "",
  });

  // Update auth state when authSettings prop changes
  useEffect(() => {
    if (authSettings) {
      setAuthType(authSettings.auth_type || "none");
      setAuthFields({
        apiKey: authSettings.api_key || "",
        iamEndpoint: authSettings.iam_endpoint || "",
        username: authSettings.username || "",
        password: authSettings.password || "",
        bearerToken: authSettings.bearer_token || "",
      });
    }
  }, [authSettings]);

  const handleAuthTypeChange = (value: string) => {
    setAuthType(value);
    setAuthFields({});
  };

  const handleAuthFieldChange = (field: string, value: string) => {
    setAuthFields((prev) => ({
      ...prev,
      [field]: value,
    }));
  };

  const handleSave = () => {
    const authSettingsToSave: AuthSettingsType = {
      auth_type: authType,
      ...(authType === "apikey" && { api_key: authFields.apiKey }),
      ...(authType === "userpass" && {
        username: authFields.username,
        password: authFields.password,
      }),
      ...(authType === "iam" && {
        iam_endpoint: authFields.iamEndpoint,
        api_key: authFields.apiKey,
      }),
      ...(authType === "bearer" && { bearer_token: authFields.bearerToken }),
    };

    onSave(authSettingsToSave);
    setOpen(false);
  };

  return (
    <BaseModal
      open={open}
      setOpen={setOpen}
      size="small-h-full"
      className="p-4"
    >
      <BaseModal.Header>
        <div className="flex items-center gap-2 text-base">Authentication</div>
      </BaseModal.Header>
      <BaseModal.Content className="h-full" overflowHidden>
        <div className="flex items-center  gap-6 border rounded-md p-4 h-[180px]">
          {/* Left column - Radio buttons */}
          <div className="flex flex-col flex-1">
            <RadioGroup value={authType} onValueChange={handleAuthTypeChange}>
              {[
                { id: "none", label: "None" },
                { id: "apikey", label: "API Key" },
                { id: "userpass", label: "Username & Password" },
                { id: "bearer", label: "Bearer Token" },
                { id: "iam", label: "IAM" },
              ].map((option) => (
                <div key={option.id} className="flex items-center space-x-2">
                  <RadioGroupItem value={option.id} id={option.id} />
                  <Label
                    htmlFor={option.id}
                    className="!text-mmd font-normal cursor-pointer flex items-center gap-3"
                  >
                    {option.label}
                    {option.id === "none" && authType === "none" && (
                      <span className="text-accent-amber-foreground flex gap-1.5 text-xs items-center">
                        <ForwardedIconComponent
                          name="AlertTriangle"
                          className="h-3.5 w-3.5 shrink-0"
                        />
                        Public endpoint - no auth. Use only in dev or trusted
                        envs.
                      </span>
                    )}
                  </Label>
                </div>
              ))}
            </RadioGroup>
          </div>
          {authType !== "none" && <Separator orientation="vertical" />}

          {/* Right column - Input fields */}
          {authType !== "none" && (
            <div className="w-3/5 min-h-[136px]">
              {authType === "apikey" && (
                <div className="flex flex-col gap-2">
                  <Label htmlFor="api-key" className="!text-mmd font-medium">
                    API Key Value
                  </Label>
                  <Input
                    id="api-key"
                    type="text"
                    placeholder="Enter API Key"
                    value={authFields.apiKey || ""}
                    onChange={(e) =>
                      handleAuthFieldChange("apiKey", e.target.value)
                    }
                  />
                </div>
              )}

              {authType === "userpass" && (
                <div className="flex flex-col gap-4">
                  <div className="flex flex-col gap-2">
                    <Label htmlFor="username" className="!text-mmd font-medium">
                      Username
                    </Label>
                    <Input
                      id="username"
                      type="text"
                      placeholder="Enter Username"
                      value={authFields.username || ""}
                      onChange={(e) =>
                        handleAuthFieldChange("username", e.target.value)
                      }
                    />
                  </div>
                  <div className="flex flex-col gap-2">
                    <Label htmlFor="password" className="!text-mmd font-medium">
                      Password
                    </Label>
                    <Input
                      id="password"
                      type="password"
                      placeholder="Enter Password"
                      value={authFields.password || ""}
                      onChange={(e) =>
                        handleAuthFieldChange("password", e.target.value)
                      }
                    />
                  </div>
                </div>
              )}

              {authType === "bearer" && (
                <div className="flex flex-col gap-2">
                  <Label
                    htmlFor="bearer-token"
                    className="!text-mmd font-medium"
                  >
                    Bearer Token
                  </Label>
                  <Input
                    id="bearer-token"
                    type="password"
                    placeholder="Enter Bearer Token"
                    value={authFields.bearerToken || ""}
                    onChange={(e) =>
                      handleAuthFieldChange("bearerToken", e.target.value)
                    }
                  />
                </div>
              )}

              {authType === "iam" && (
                <div className="flex flex-col gap-4">
                  <div className="flex flex-col gap-2">
                    <Label
                      htmlFor="iam-endpoint"
                      className="!text-mmd font-medium"
                    >
                      IAM Endpoint
                    </Label>
                    <Input
                      id="iam-endpoint"
                      type="text"
                      placeholder="Enter IAM Endpoint"
                      value={authFields.iamEndpoint || ""}
                      onChange={(e) =>
                        handleAuthFieldChange("iamEndpoint", e.target.value)
                      }
                    />
                  </div>
                  <div className="flex flex-col gap-2">
                    <Label htmlFor="api-key" className="!text-mmd font-medium">
                      API Key or Token
                    </Label>
                    <Input
                      id="password"
                      type="password"
                      placeholder="Enter API Key or Token"
                      value={authFields.apiKey || ""}
                      onChange={(e) =>
                        handleAuthFieldChange("apiKey", e.target.value)
                      }
                    />
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </BaseModal.Content>
      <BaseModal.Footer
        submit={{
          label: "Save Authentication",
          onClick: handleSave,
        }}
      />
    </BaseModal>
  );
};

export default AuthModal;
