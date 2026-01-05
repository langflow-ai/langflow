import {
  useIsFetching,
  usePrefetchQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { nanoid } from "nanoid";
import { useEffect, useState } from "react";
import { ForwardedIconComponent } from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
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
  KeyPairRow,
} from "@/modals/IOModal/components/IOFieldView/components/key-pair-input";
import type { MCPServerType } from "@/types/mcp";
import { extractMcpServersFromJson } from "@/utils/mcpUtils";
import { parseString } from "@/utils/stringManipulation";
import { cn } from "@/utils/utils";

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
  const [open, setOpen] =
    mySetOpen !== undefined && myOpen !== undefined
      ? [myOpen, mySetOpen]
      : useState(false);

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
        setError("Name and command are required.");
        return;
      }
      if (stdioEnv.some((item) => item.error)) {
        setError("Duplicate keys found in environment variables.");
        return;
      }
      const name = parseString(stdioName, [
        "mcp_name_case",
        "no_blank",
        "lowercase",
      ]).slice(0, MAX_MCP_SERVER_NAME_LENGTH);
      try {
        await modifyMCPServer({
          name,
          command: stdioCommand,
          args: stdioArgs.filter((a) => a.trim() !== ""),
          env: keyPairRowToObject(stdioEnv),
        });
        if (!initialData) {
          await queryClient.setQueryData(["useGetMCPServers"], (old: any) => {
            return [...old, { name, toolsCount: 0 }];
          });
        }
        onSuccess?.(name);
        setOpen(false);
        setStdioName("");
        setStdioCommand("");
        setStdioArgs([""]);
        setStdioEnv([{ key: "", value: "", id: nanoid(), error: false }]);
        setError(null);
      } catch (err: any) {
        setError(err?.message || "Failed to add MCP server.");
      }
      return;
    }
    if (type === "HTTP") {
      if (!httpName.trim() || !httpUrl.trim()) {
        setError("Name and URL are required.");
        return;
      }
      if (httpEnv.some((item) => item.error)) {
        setError("Duplicate keys found in environment variables.");
        return;
      }
      if (httpHeaders.some((item) => item.error)) {
        setError("Duplicate keys found in headers.");
        return;
      }
      const name = parseString(httpName, [
        "mcp_name_case",
        "no_blank",
        "lowercase",
      ]).slice(0, MAX_MCP_SERVER_NAME_LENGTH);
      try {
        await modifyMCPServer({
          name,
          env: keyPairRowToObject(httpEnv),
          url: httpUrl,
          headers: keyPairRowToObject(httpHeaders),
        });
        if (!initialData) {
          await queryClient.setQueryData(["useGetMCPServers"], (old: any) => {
            return [...old, { name, toolsCount: 0 }];
          });
        }
        onSuccess?.(name);
        setOpen(false);
        setHttpName("");
        setHttpUrl("");
        setHttpEnv([{ key: "", value: "", id: nanoid(), error: false }]);
        setHttpHeaders([{ key: "", value: "", id: nanoid(), error: false }]);
        setError(null);
      } catch (err: any) {
        setError(err?.message || "Failed to add MCP server.");
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
    } catch (e: any) {
      setError(e.message || "Invalid input");
      return;
    }
    if (servers.length === 0) {
      setError("No valid MCP server found in the input.");
      return;
    }
    try {
      await Promise.all(servers.map((server) => modifyMCPServer(server)));
      if (!initialData) {
        await queryClient.setQueryData(["useGetMCPServers"], (old: any) => {
          return [
            ...old,
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
    } catch (err: any) {
      setError(err?.message || "Failed to add one or more MCP servers.");
    }
  }

  return (
    <BaseModal
      open={open}
      setOpen={setOpen}
      size="x-small"
      onSubmit={submitForm}
      className="!p-0"
    >
      <BaseModal.Trigger>{children}</BaseModal.Trigger>
      <BaseModal.Content className="flex flex-col justify-between overflow-hidden">
        <div className="flex h-full w-full flex-col overflow-hidden">
          <div className="flex flex-col gap-3 p-4 tracking-normal">
            <div className="flex items-center gap-2 text-sm font-medium">
              <ForwardedIconComponent
                name="Mcp"
                className="h-4 w-4 text-primary"
                aria-hidden="true"
              />
              {initialData ? "Update MCP Server" : "Add MCP Server"}
            </div>
            <span className="text-mmd font-normal text-muted-foreground">
              Save MCP Servers. Manage added servers in{" "}
              <CustomLink className="underline" to="/settings/mcp-servers">
                settings
              </CustomLink>
              .
            </span>
          </div>
          <div className="flex h-full w-full flex-col gap-4 overflow-hidden">
            <Tabs
              defaultValue={type}
              onValueChange={changeType}
              className="w-full"
            >
              <div className="px-4">
                <TabsList className="mb-4 grid w-full grid-cols-3">
                  <TabsTrigger
                    disabled={!!initialData && type !== "JSON"}
                    data-testid="json-tab"
                    value="JSON"
                  >
                    JSON
                  </TabsTrigger>
                  <TabsTrigger
                    data-testid="stdio-tab"
                    disabled={!!initialData && type !== "STDIO"}
                    value="STDIO"
                  >
                    STDIO
                  </TabsTrigger>
                  <TabsTrigger
                    data-testid="http-tab"
                    disabled={!!initialData && type !== "HTTP"}
                    value="HTTP"
                  >
                    Streamable HTTP/SSE
                  </TabsTrigger>
                </TabsList>
              </div>
              <div
                className="relative flex max-h-[280px] min-h-[280px] w-full flex-1 flex-col gap-2 overflow-y-auto border-y p-4 pt-2"
                id="global-variable-modal-inputs"
              >
                {error && (
                  <ShadTooltip content={error}>
                    <div
                      className={cn(
                        "absolute right-4 top-4 truncate text-xs font-medium text-red-500",
                        type === "JSON" ? "w-3/5" : "w-4/5",
                      )}
                    >
                      {error}
                    </div>
                  </ShadTooltip>
                )}
                <TabsContent value="JSON">
                  <div className="flex flex-col gap-2">
                    <Label className="!text-mmd">Paste in JSON config</Label>
                    <Textarea
                      value={jsonValue}
                      data-testid="json-input"
                      onChange={(e) => setJsonValue(e.target.value)}
                      className="min-h-[225px] font-mono text-mmd"
                      placeholder="Paste in JSON config to add server"
                      disabled={isPending}
                    />
                  </div>
                </TabsContent>
                <TabsContent value="STDIO">
                  <div className="flex flex-col gap-4">
                    <div className="flex flex-col gap-2">
                      <Label className="flex items-start gap-1 !text-mmd">
                        Name <span className="text-red-500">*</span>
                      </Label>
                      <Input
                        value={stdioName}
                        onChange={(e) => setStdioName(e.target.value)}
                        placeholder="Type server name..."
                        data-testid="stdio-name-input"
                        disabled={isPending}
                      />
                    </div>
                    <div className="flex flex-col gap-2">
                      <Label className="flex items-start gap-1 !text-mmd">
                        Command<span className="text-red-500">*</span>
                      </Label>
                      <Input
                        value={stdioCommand}
                        onChange={(e) => setStdioCommand(e.target.value)}
                        placeholder="Type command..."
                        data-testid="stdio-command-input"
                        disabled={isPending}
                      />
                    </div>
                    <div className="flex flex-col gap-2">
                      <Label className="!text-mmd">Arguments</Label>
                      <InputListComponent
                        value={stdioArgs}
                        handleOnNewValue={({ value }) => setStdioArgs(value)}
                        disabled={isPending}
                        placeholder="Type argument..."
                        listAddLabel="Add Argument"
                        editNode={false}
                        id="stdio-args"
                        data-testid="stdio-args-input"
                      />
                    </div>
                    <div className="flex flex-col gap-2">
                      <Label className="!text-mmd">Environment Variables</Label>
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
                <TabsContent value="HTTP">
                  <div className="flex flex-col gap-4">
                    <div className="flex flex-col gap-2">
                      <Label className="flex items-start gap-1 !text-mmd">
                        Name<span className="text-red-500">*</span>
                      </Label>
                      <Input
                        value={httpName}
                        onChange={(e) => setHttpName(e.target.value)}
                        placeholder="Name"
                        data-testid="http-name-input"
                        disabled={isPending}
                      />
                    </div>
                    <div className="flex flex-col gap-2">
                      <Label className="flex items-start gap-1 !text-mmd">
                        Streamable HTTP/SSE URL
                        <span className="text-red-500">*</span>
                      </Label>
                      <Input
                        value={httpUrl}
                        onChange={(e) => setHttpUrl(e.target.value)}
                        placeholder="Streamable HTTP/SSE URL"
                        data-testid="http-url-input"
                        disabled={isPending}
                      />
                    </div>
                    <div className="flex flex-col gap-2">
                      <Label className="!text-mmd">Headers</Label>
                      <IOKeyPairInput
                        value={httpHeaders}
                        onChange={setHttpHeaders}
                        duplicateKey={false}
                        isList={true}
                        isInputField={true}
                        testId="http-headers"
                      />
                    </div>
                    <div className="flex flex-col gap-2">
                      <Label className="!text-mmd">Environment Variables</Label>
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
        </div>
        <div className="flex justify-end gap-2 p-4">
          <Button variant="outline" size="sm" onClick={() => setOpen(false)}>
            <span className="text-mmd font-normal">Cancel</span>
          </Button>
          <Button
            size="sm"
            onClick={submitForm}
            data-testid="add-mcp-server-button"
            loading={isPending}
          >
            <span className="text-mmd">
              {initialData ? "Update Server" : "Add Server"}
            </span>
          </Button>
        </div>
      </BaseModal.Content>
    </BaseModal>
  );
}
