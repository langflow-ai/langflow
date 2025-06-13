import { useEffect, useState } from "react";

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
import { useAddMCPServer } from "@/controllers/API/queries/mcp/use-add-mcp-server";
import { usePatchMCPServer } from "@/controllers/API/queries/mcp/use-patch-mcp-server";
import { CustomLink } from "@/customization/components/custom-link";
import BaseModal from "@/modals/baseModal";
import IOKeyPairInput from "@/modals/IOModal/components/IOFieldView/components/key-pair-input";
import { MCPServerType } from "@/types/mcp";
import { extractMcpServersFromJson } from "@/utils/mcpUtils";
import { parseString } from "@/utils/stringManipulation";
import {
  useIsFetching,
  usePrefetchQuery,
  useQueryClient,
} from "@tanstack/react-query";

//TODO IMPLEMENT FORM LOGIC

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
    initialData ? (initialData.command ? "STDIO" : "SSE") : "JSON",
  );
  const [jsonValue, setJsonValue] = useState("");
  const [error, setError] = useState<string | null>(null);
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
    setStdioEnv([{ "": "" }]);
    setSseName("");
    setSseUrl("");
    setSseEnv([{ "": "" }]);
    setSseHeaders([{ "": "" }]);
  };

  // STDIO state
  const [stdioName, setStdioName] = useState(initialData?.name || "");
  const [stdioCommand, setStdioCommand] = useState(initialData?.command || "");
  const [stdioArgs, setStdioArgs] = useState<string[]>(
    initialData?.args || [""],
  );
  const [stdioEnv, setStdioEnv] = useState<any>(
    initialData?.env || [{ "": "" }],
  );

  // SSE state
  const [sseName, setSseName] = useState(initialData?.name || "");
  const [sseUrl, setSseUrl] = useState(initialData?.url || "");
  const [sseEnv, setSseEnv] = useState<any>(initialData?.env || [{ "": "" }]);
  const [sseHeaders, setSseHeaders] = useState<any>(
    initialData?.headers || [{ "": "" }],
  );

  useEffect(() => {
    if (open) {
      setType(initialData ? (initialData.command ? "STDIO" : "SSE") : "JSON");
      setError(null);
      setJsonValue("");
      setStdioName(initialData?.name || "");
      setStdioCommand(initialData?.command || "");
      setStdioArgs(initialData?.args || [""]);
      setStdioEnv(initialData?.env || [{ "": "" }]);
      setSseName(initialData?.name || "");
      setSseUrl(initialData?.url || "");
      setSseEnv(initialData?.env || [{ "": "" }]);
      setSseHeaders(initialData?.headers || [{ "": "" }]);
    }
  }, [open]);

  function parseEnvList(envList: any): Record<string, string> {
    // envList is an array of objects with one key each
    const env: Record<string, string> = {};
    if (Array.isArray(envList)) {
      envList.forEach((obj) => {
        const key = Object.keys(obj)[0];
        if (key && key.trim() !== "") {
          env[key] = obj[key];
        }
      });
    }
    return env;
  }

  async function submitForm() {
    setError(null);
    if (type === "STDIO") {
      if (!stdioName.trim() || !stdioCommand.trim()) {
        setError("Name and command are required.");
        return;
      }
      const name = parseString(stdioName, [
        "snake_case",
        "no_blank",
        "lowercase",
      ]).slice(0, 30);
      try {
        await modifyMCPServer({
          name,
          command: stdioCommand,
          args: stdioArgs.filter((a) => a.trim() !== ""),
          env: parseEnvList(stdioEnv),
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
        setStdioEnv([{ "": "" }]);
        setError(null);
      } catch (err: any) {
        setError(err?.message || "Failed to add MCP server.");
      }
      return;
    }
    if (type === "SSE") {
      if (!sseName.trim() || !sseUrl.trim()) {
        setError("Name and URL are required.");
        return;
      }
      const name = parseString(sseName, [
        "snake_case",
        "no_blank",
        "lowercase",
      ]).slice(0, 30);
      try {
        await modifyMCPServer({
          name,
          env: parseEnvList(sseEnv),
          url: sseUrl,
          headers: parseEnvList(sseHeaders),
        });
        if (!initialData) {
          await queryClient.setQueryData(["useGetMCPServers"], (old: any) => {
            return [...old, { name, toolsCount: 0 }];
          });
        }
        onSuccess?.(name);
        setOpen(false);
        setSseName("");
        setSseUrl("");
        setSseEnv([{ "": "" }]);
        setSseHeaders([{ "": "" }]);
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
          "snake_case",
          "no_blank",
          "lowercase",
        ]).slice(0, 30),
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
              Save MCP Servers. Manage added connections in{" "}
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
                    data-testid="sse-tab"
                    disabled={!!initialData && type !== "SSE"}
                    value="SSE"
                  >
                    SSE
                  </TabsTrigger>
                </TabsList>
              </div>
              <div
                className="relative flex max-h-[280px] min-h-[280px] w-full flex-1 flex-col gap-2 overflow-y-auto border-y p-4 pt-2"
                id="global-variable-modal-inputs"
              >
                {error && (
                  <div className="absolute right-4 top-2.5 text-xs font-medium text-red-500">
                    {error}
                  </div>
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
                      />
                    </div>
                  </div>
                </TabsContent>
                <TabsContent value="SSE">
                  <div className="flex flex-col gap-4">
                    <div className="flex flex-col gap-2">
                      <Label className="flex items-start gap-1 !text-mmd">
                        Name<span className="text-red-500">*</span>
                      </Label>
                      <Input
                        value={sseName}
                        onChange={(e) => setSseName(e.target.value)}
                        placeholder="Name"
                        disabled={isPending}
                      />
                    </div>
                    <div className="flex flex-col gap-2">
                      <Label className="flex items-start gap-1 !text-mmd">
                        SSE URL<span className="text-red-500">*</span>
                      </Label>
                      <Input
                        value={sseUrl}
                        onChange={(e) => setSseUrl(e.target.value)}
                        placeholder="SSE URL"
                        disabled={isPending}
                      />
                    </div>
                    <div className="flex flex-col gap-2">
                      <Label className="!text-mmd">Headers</Label>
                      <IOKeyPairInput
                        value={sseHeaders}
                        onChange={setSseHeaders}
                        duplicateKey={false}
                        isList={true}
                        isInputField={true}
                      />
                    </div>
                    <div className="flex flex-col gap-2">
                      <Label className="!text-mmd">Environment Variables</Label>
                      <IOKeyPairInput
                        value={sseEnv}
                        onChange={setSseEnv}
                        duplicateKey={false}
                        isList={true}
                        isInputField={true}
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
