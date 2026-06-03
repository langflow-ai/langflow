import { useQueryClient } from "@tanstack/react-query";
import { nanoid } from "nanoid";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useLocation } from "react-router-dom";
import { ForwardedIconComponent } from "@/components/common/genericIconComponent";
import InputListComponent from "@/components/core/parameterRenderComponent/components/inputListComponent";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs-button";
import { Textarea } from "@/components/ui/textarea";
import { MAX_MCP_SERVER_NAME_LENGTH } from "@/constants/constants";
import { useAddMCPServer } from "@/controllers/API/queries/mcp/use-add-mcp-server";
import { usePatchMCPServer } from "@/controllers/API/queries/mcp/use-patch-mcp-server";
import { CustomLink } from "@/customization/components/custom-link";
import BaseModal from "@/modals/baseModal";
import IOKeyPairInput, {
  type KeyPairRow,
} from "@/modals/IOModal/components/IOFieldView/components/key-pair-input";
import IOKeyPairInputWithVariables from "@/modals/IOModal/components/IOFieldView/components/key-pair-input-with-variables";
import type { MCPServerType } from "@/types/mcp";
import { extractMcpServersFromJson } from "@/utils/mcpUtils";
import { parseString } from "@/utils/stringManipulation";

const MCP_SETTINGS_PAGE = "/settings/mcp-servers";

//TODO IMPLEMENT FORM LOGIC
const objectToKeyPairRow = (
  obj?: Record<string, string>,
  oldData: KeyPairRow[] = [],
) => {
  const keys = Object.keys(obj || {});
  if (!obj || keys.length === 0) {
    return [{ key: "", value: "", id: nanoid(), error: false }];
  }
  return keys.map((key) => {
    const oldItem = oldData.find((item) => item.key === key);
    return (
      oldItem || { key, value: obj[key] || "", id: nanoid(), error: false }
    );
  });
};

const keyPairRowToObject = (arr: KeyPairRow[]): Record<string, string> => {
  return arr.reduce((obj, item) => {
    if (!item.error && item.key) {
      obj[item.key] = item.value;
    }
    return obj;
  }, {});
};

const buildKeyPairPayload = (
  rows: KeyPairRow[],
  existing?: Record<string, string>,
) => {
  const nextValue = keyPairRowToObject(rows);
  if (Object.keys(nextValue).length > 0) {
    return nextValue;
  }
  if (existing && Object.keys(existing).length > 0) {
    return {};
  }
  return undefined;
};

const buildArgsPayload = (args: string[], existing?: string[]) => {
  const nextValue = args.filter((arg) => arg.trim() !== "");
  if (nextValue.length > 0) {
    return nextValue;
  }
  if (existing && existing.length > 0) {
    return [];
  }
  return undefined;
};

export default function AddMcpServerModal({
  children,
  initialData,
  open: myOpen,
  setOpen: mySetOpen,
  onSuccess,
}: {
  children?: JSX.Element;
  initialData?: MCPServerType;
  open?: boolean;
  setOpen?: (a: boolean | ((o?: boolean) => boolean)) => void;
  onSuccess?: (server: string) => void;
}): JSX.Element {
  const { t } = useTranslation();
  const [open, setOpen] =
    mySetOpen !== undefined && myOpen !== undefined
      ? [myOpen, mySetOpen]
      : useState(false);

  const location = useLocation();
  const isOnMcpSettingsPage = location.pathname === MCP_SETTINGS_PAGE;

  const [type, setType] = useState(
    initialData ? (initialData.command ? "STDIO" : "HTTP") : "JSON",
  );
  const [jsonValue, setJsonValue] = useState("");
  const [error, setError] = useState<string | null>(
    "Error downloading file: File _mcp_servers.json not found in flow 7e93e2c5-b979-49c0-b01b-4f4111d9230d",
  );
  const { mutateAsync: addMCPServer, isPending: isAddPending } =
    useAddMCPServer();
  const { mutateAsync: patchMCPServer, isPending: isPatchPending } =
    usePatchMCPServer();

  const queryClient = useQueryClient();

  const modifyMCPServer = initialData ? patchMCPServer : addMCPServer;
  const isPending = isAddPending || isPatchPending;

  const changeType = (type: string) => {
    setType(type);
    setError(null);
    setJsonValue("");
    setStdioName("");
    setStdioCommand("");
    setStdioArgs([""]);
    setStdioEnv([{ key: "", value: "", id: nanoid(), error: false }]);
    setHttpName("");
    setHttpUrl("");
    setHttpEnv([{ key: "", value: "", id: nanoid(), error: false }]);
    setHttpHeaders([{ key: "", value: "", id: nanoid(), error: false }]);
  };

  // STDIO state
  const [stdioName, setStdioName] = useState(initialData?.name || "");
  const [stdioCommand, setStdioCommand] = useState(initialData?.command || "");
  const [stdioArgs, setStdioArgs] = useState<string[]>(
    initialData?.args || [""],
  );
  const [stdioEnv, setStdioEnv] = useState<KeyPairRow[]>(
    objectToKeyPairRow(initialData?.env) || [],
  );

  // HTTP state
  const [httpName, setHttpName] = useState(initialData?.name || "");
  const [httpUrl, setHttpUrl] = useState(initialData?.url || "");
  const [httpEnv, setHttpEnv] = useState<KeyPairRow[]>(
    objectToKeyPairRow(initialData?.env) || [],
  );
  const [httpHeaders, setHttpHeaders] = useState<KeyPairRow[]>(
    objectToKeyPairRow(initialData?.headers) || [],
  );

  useEffect(() => {
    if (open) {
      setType(initialData ? (initialData.command ? "STDIO" : "HTTP") : "JSON");
      setError(null);
      setJsonValue("");
      setStdioName(initialData?.name || "");
      setStdioCommand(initialData?.command || "");
      setStdioArgs(initialData?.args || [""]);
      setStdioEnv(objectToKeyPairRow(initialData?.env) || []);
      setHttpName(initialData?.name || "");
      setHttpUrl(initialData?.url || "");
      setHttpEnv(objectToKeyPairRow(initialData?.env) || []);
      setHttpHeaders(objectToKeyPairRow(initialData?.headers) || []);
    }
  }, [open]);

  async function submitForm() {
    setError(null);
    if (type === "STDIO") {
      if (!stdioName.trim() || !stdioCommand.trim()) {
        setError(t("mcp.modal.errorNameCommandRequired"));
        return;
      }
      if (stdioEnv.some((item) => item.error)) {
        setError(t("mcp.modal.errorDuplicateEnvKeys"));
        return;
      }
      // The server name is the immutable identifier: it is the storage key and
      // the URL path PATCH targets. When editing, always reuse the original
      // name so the update hits the existing record. Re-deriving it from the
      // input would let a name change retarget the request and create a
      // duplicate server instead of updating the original.
      const name = initialData
        ? initialData.name
        : parseString(stdioName, [
            "mcp_name_case",
            "no_blank",
            "lowercase",
          ]).slice(0, MAX_MCP_SERVER_NAME_LENGTH);
      const argsPayload = buildArgsPayload(stdioArgs, initialData?.args);
      const envPayload = buildKeyPairPayload(stdioEnv, initialData?.env);
      try {
        await modifyMCPServer({
          name,
          command: stdioCommand,
          ...(argsPayload !== undefined ? { args: argsPayload } : {}),
          ...(envPayload !== undefined ? { env: envPayload } : {}),
        });
        if (!initialData) {
          await queryClient.setQueryData(
            ["useGetMCPServers"],
            (old: unknown) => {
              return [
                ...(Array.isArray(old) ? old : []),
                { name, toolsCount: 0 },
              ];
            },
          );
        }
        onSuccess?.(name);
        setOpen(false);
        setStdioName("");
        setStdioCommand("");
        setStdioArgs([""]);
        setStdioEnv([{ key: "", value: "", id: nanoid(), error: false }]);
        setError(null);
      } catch (err: unknown) {
        setError(
          err instanceof Error ? err.message : t("mcp.modal.errorFailedAdd"),
        );
      }
      return;
    }
    if (type === "HTTP") {
      if (!httpName.trim() || !httpUrl.trim()) {
        setError(t("mcp.modal.errorNameUrlRequired"));
        return;
      }
      if (httpEnv.some((item) => item.error)) {
        setError(t("mcp.modal.errorDuplicateEnvKeys"));
        return;
      }
      if (httpHeaders.some((item) => item.error)) {
        setError(t("mcp.modal.errorDuplicateHeaders"));
        return;
      }
      // The server name is the immutable identifier: it is the storage key and
      // the URL path PATCH targets. When editing, always reuse the original
      // name so the update hits the existing record. Re-deriving it from the
      // input would let a name change retarget the request and create a
      // duplicate server instead of updating the original.
      const name = initialData
        ? initialData.name
        : parseString(httpName, [
            "mcp_name_case",
            "no_blank",
            "lowercase",
          ]).slice(0, MAX_MCP_SERVER_NAME_LENGTH);
      const envPayload = buildKeyPairPayload(httpEnv, initialData?.env);
      const headersPayload = buildKeyPairPayload(
        httpHeaders,
        initialData?.headers,
      );
      try {
        await modifyMCPServer({
          name,
          url: httpUrl,
          ...(envPayload !== undefined ? { env: envPayload } : {}),
          ...(headersPayload !== undefined ? { headers: headersPayload } : {}),
        });
        if (!initialData) {
          await queryClient.setQueryData(
            ["useGetMCPServers"],
            (old: unknown) => {
              return [
                ...(Array.isArray(old) ? old : []),
                { name, toolsCount: 0 },
              ];
            },
          );
        }
        onSuccess?.(name);
        setOpen(false);
        setHttpName("");
        setHttpUrl("");
        setHttpEnv([{ key: "", value: "", id: nanoid(), error: false }]);
        setHttpHeaders([{ key: "", value: "", id: nanoid(), error: false }]);
        setError(null);
      } catch (err: unknown) {
        setError(
          err instanceof Error ? err.message : t("mcp.modal.errorFailedAdd"),
        );
      }
      return;
    }
    // JSON mode (multi-server)
    let servers: MCPServerType[];
    try {
      servers = extractMcpServersFromJson(jsonValue).map((server) => ({
        ...server,
        name: parseString(server.name, [
          "mcp_name_case",
          "no_blank",
          "lowercase",
        ]).slice(0, MAX_MCP_SERVER_NAME_LENGTH),
      }));
    } catch (e: unknown) {
      setError(
        e instanceof Error ? e.message : t("mcp.modal.errorNoServerFound"),
      );
      return;
    }
    if (servers.length === 0) {
      setError(t("mcp.modal.errorNoServerFound"));
      return;
    }
    try {
      await Promise.all(servers.map((server) => modifyMCPServer(server)));
      if (!initialData) {
        await queryClient.setQueryData(["useGetMCPServers"], (old: unknown) => {
          return [
            ...(Array.isArray(old) ? old : []),
            ...servers.map((server) => ({
              name: server.name,
              toolsCount: 0,
            })),
          ];
        });
      }
      onSuccess?.(servers.map((server) => server.name)[0]);
      setOpen(false);
      setJsonValue("");
      setError(null);
    } catch (err: unknown) {
      setError(
        err instanceof Error
          ? err.message
          : t("mcp.modal.errorFailedAddMultiple"),
      );
    }
  }

  return (
    <BaseModal
      open={open}
      setOpen={setOpen}
      size="x-small-h-full"
      onSubmit={submitForm}
      className="!p-0 min-h-[250px] max-h-[75vh] flex-grow"
    >
      <BaseModal.Trigger>{children}</BaseModal.Trigger>
      <BaseModal.Content className="flex flex-1 flex-col overflow-hidden min-h-0">
        <div className="flex flex-1 w-full flex-col overflow-hidden min-h-0">
          <div className="flex flex-col gap-3 p-4 tracking-normal">
            <div className="flex items-center gap-2 text-sm font-medium">
              <ForwardedIconComponent
                name="Mcp"
                className="h-4 w-4 text-primary"
                aria-hidden="true"
              />
              {initialData
                ? t("mcp.modal.updateTitle")
                : t("mcp.modal.addTitle")}
            </div>
            <span className="text-mmd font-normal text-muted-foreground">
              {isOnMcpSettingsPage ? (
                t("mcp.modal.descriptionSettings")
              ) : (
                <>
                  {t("mcp.modal.descriptionFlow")}{" "}
                  <CustomLink
                    className="underline"
                    to={MCP_SETTINGS_PAGE}
                    onClick={() => setOpen(false)}
                  >
                    {t("mcp.modal.descriptionFlowLink")}
                  </CustomLink>
                  .
                </>
              )}
            </span>
          </div>
          <Tabs
            defaultValue={type}
            onValueChange={changeType}
            className="flex flex-1 w-full flex-col overflow-hidden min-h-0"
          >
            <div className="px-4">
              <TabsList className="mb-4 flex w-full gap-2">
                <TabsTrigger
                  className="flex-1"
                  disabled={!!initialData && type !== "JSON"}
                  data-testid="json-tab"
                  value="JSON"
                >
                  {t("mcp.modal.tabJson")}
                </TabsTrigger>
                <TabsTrigger
                  className="flex-1"
                  data-testid="stdio-tab"
                  disabled={!!initialData && type !== "STDIO"}
                  value="STDIO"
                >
                  {t("mcp.modal.tabStdio")}
                </TabsTrigger>
                <TabsTrigger
                  className="flex-1"
                  data-testid="http-tab"
                  disabled={!!initialData && type !== "HTTP"}
                  value="HTTP"
                >
                  {t("mcp.modal.tabStreamableHttp")}
                </TabsTrigger>
              </TabsList>
            </div>
            <div
              className="flex w-full flex-1 flex-col overflow-y-auto border-y p-4 min-h-0"
              id="global-variable-modal-inputs"
            >
              {error && (
                <div className="mb-4 rounded-md bg-destructive/10 px-4 py-2 text-xs font-medium text-destructive">
                  {error}
                </div>
              )}
              <TabsContent value="JSON" className="flex flex-col p-0 m-0">
                <Label className="!text-mmd mb-2">
                  {t("mcp.modal.jsonTabLabel")}
                </Label>
                <Textarea
                  value={jsonValue}
                  data-testid="json-input"
                  onChange={(e) => setJsonValue(e.target.value)}
                  className="min-h-[300px] font-mono text-mmd resize-none"
                  placeholder={t("mcp.modal.jsonPlaceholder")}
                  disabled={isPending}
                />
              </TabsContent>
              <TabsContent
                value="STDIO"
                className="flex flex-1 flex-col h-full p-0 m-0"
              >
                <div className="flex h-full flex-col gap-4">
                  <div className="flex flex-col gap-2">
                    <Label className="flex items-start gap-1 !text-mmd">
                      {t("mcp.modal.fieldName")}{" "}
                      <span className="text-destructive">*</span>
                    </Label>
                    <Input
                      value={stdioName}
                      onChange={(e) => setStdioName(e.target.value)}
                      placeholder={t("mcp.modal.placeholderServerName")}
                      data-testid="stdio-name-input"
                      disabled={isPending || !!initialData}
                    />
                  </div>
                  <div className="flex flex-col gap-2">
                    <Label className="flex items-start gap-1 !text-mmd">
                      {t("mcp.modal.fieldCommand")}
                      <span className="text-destructive">*</span>
                    </Label>
                    <Input
                      value={stdioCommand}
                      onChange={(e) => setStdioCommand(e.target.value)}
                      placeholder={t("mcp.modal.placeholderCommand")}
                      data-testid="stdio-command-input"
                      disabled={isPending}
                    />
                  </div>
                  <div className="flex flex-col gap-2">
                    <Label className="!text-mmd">
                      {t("mcp.modal.fieldArguments")}
                    </Label>
                    <InputListComponent
                      value={stdioArgs}
                      handleOnNewValue={({ value }) => setStdioArgs(value)}
                      disabled={isPending}
                      placeholder={t("mcp.modal.placeholderArgument")}
                      listAddLabel={t("mcp.modal.addArgumentButton")}
                      editNode={false}
                      id="stdio-args"
                      data-testid="stdio-args-input"
                    />
                  </div>
                  <div className="flex flex-col gap-2">
                    <Label className="!text-mmd">
                      {t("mcp.modal.fieldEnvironmentVariables")}
                    </Label>
                    <IOKeyPairInput
                      value={stdioEnv}
                      onChange={setStdioEnv}
                      duplicateKey={false}
                      isList={true}
                      isInputField={true}
                      testId="stdio-env"
                    />
                  </div>
                </div>
              </TabsContent>
              <TabsContent
                value="HTTP"
                className="flex flex-1 flex-col h-full p-0 m-0"
              >
                <div className="flex h-full flex-col gap-4">
                  <div className="flex flex-col gap-2">
                    <Label className="flex items-start gap-1 !text-mmd">
                      {t("mcp.modal.fieldName")}
                      <span className="text-destructive">*</span>
                    </Label>
                    <Input
                      value={httpName}
                      onChange={(e) => setHttpName(e.target.value)}
                      placeholder={t("mcp.modal.placeholderHttpName")}
                      data-testid="http-name-input"
                      disabled={isPending || !!initialData}
                    />
                  </div>
                  <div className="flex flex-col gap-2">
                    <Label className="flex items-start gap-1 !text-mmd">
                      {t("mcp.modal.fieldStreamableUrl")}
                      <span className="text-destructive">*</span>
                    </Label>
                    <Input
                      value={httpUrl}
                      onChange={(e) => setHttpUrl(e.target.value)}
                      placeholder={t("mcp.modal.placeholderHttpUrl")}
                      data-testid="http-url-input"
                      disabled={isPending}
                    />
                  </div>
                  <div className="flex flex-col gap-2">
                    <Label className="!text-mmd">
                      {t("mcp.modal.fieldHeaders")}
                    </Label>
                    <IOKeyPairInputWithVariables
                      value={httpHeaders}
                      onChange={setHttpHeaders}
                      duplicateKey={false}
                      isList={true}
                      isInputField={true}
                      testId="http-headers"
                      enableGlobalVariables={true}
                    />
                  </div>
                  <div className="flex flex-col gap-2">
                    <Label className="!text-mmd">
                      {t("mcp.modal.fieldEnvironmentVariables")}
                    </Label>
                    <IOKeyPairInput
                      value={httpEnv}
                      onChange={setHttpEnv}
                      duplicateKey={false}
                      isList={true}
                      isInputField={true}
                      testId="http-env"
                    />
                  </div>
                </div>
              </TabsContent>
            </div>
          </Tabs>
        </div>
        <div className="flex shrink-0 justify-end gap-2 p-4">
          <Button variant="outline" size="sm" onClick={() => setOpen(false)}>
            <span className="text-mmd font-normal">
              {t("mcp.modal.cancelButton")}
            </span>
          </Button>
          <Button
            size="sm"
            onClick={submitForm}
            data-testid="add-mcp-server-button"
            loading={isPending}
          >
            <span className="text-mmd">
              {initialData
                ? t("mcp.modal.updateServerButton")
                : t("mcp.modal.addServerButton")}
            </span>
          </Button>
        </div>
      </BaseModal.Content>
    </BaseModal>
  );
}
