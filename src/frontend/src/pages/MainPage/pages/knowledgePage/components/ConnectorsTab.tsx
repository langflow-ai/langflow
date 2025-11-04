import { Loader2 } from "lucide-react";
import { useEffect, useState } from "react";
import { Cookies } from "react-cookie";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { LANGFLOW_ACCESS_TOKEN } from "@/constants/constants";
import { api } from "@/controllers/API/api";

interface Connector {
  id: string;
  name: string;
  connector_type: string;
  is_authenticated: boolean;
  last_sync: string | null;
  sync_status: string | null;
  created_at: string;
}

export default function ConnectorsTab() {
  const [connectors, setConnectors] = useState<Connector[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [newConnectorName, setNewConnectorName] = useState("");
  const [isCreating, setIsCreating] = useState(false);
  const [syncingIds, setSyncingIds] = useState<Set<string>>(new Set());
  const [syncProgress, setSyncProgress] = useState<
    Record<string, { progress: number; message: string }>
  >({});

  // Load connectors
  const loadConnectors = async () => {
    try {
      const response = await api.get<Connector[]>("/api/v1/connectors");
      setConnectors(response.data);
    } catch (error) {
      console.error("Failed to load connectors:", error);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadConnectors();
  }, []);

  // Create new connector
  const handleCreateConnector = async () => {
    if (!newConnectorName.trim()) return;

    setIsCreating(true);
    try {
      // Step 1: Create the connection
      const createResponse = await api.post<Connector>("/api/v1/connectors", {
        connector_type: "google_drive",
        name: newConnectorName,
        config: { folder_id: "root", recursive: false },
      });

      const connector = createResponse.data;

      // Step 2: Get OAuth URL
      const oauthResponse = await api.get<{
        authorization_url: string;
        state: string;
      }>(`/api/v1/connectors/${connector.id}/oauth/url`);
      const { authorization_url, state } = oauthResponse.data;

      // Step 3: Open OAuth popup
      const width = 600;
      const height = 700;
      const left = window.screenX + (window.outerWidth - width) / 2;
      const top = window.screenY + (window.outerHeight - height) / 2;

      const popup = window.open(
        authorization_url,
        "Google OAuth",
        `width=${width},height=${height},left=${left},top=${top}`,
      );

      // Step 4: Listen for OAuth callback
      const checkPopup = setInterval(() => {
        if (popup?.closed) {
          clearInterval(checkPopup);
          // Wait a moment for backend to commit, then reload
          setTimeout(() => {
            loadConnectors();
            setIsDialogOpen(false);
            setNewConnectorName("");
          }, 1000);
        }
      }, 500);
    } catch (error) {
      console.error("Failed to create connector:", error);
      alert("Failed to create connector. See console for details.");
    } finally {
      setIsCreating(false);
    }
  };

  // Trigger sync with real-time progress
  const handleSync = async (connectorId: string) => {
    setSyncingIds((prev) => new Set(prev).add(connectorId));
    setSyncProgress((prev) => ({
      ...prev,
      [connectorId]: { progress: 0, message: "Starting..." },
    }));

    try {
      // Start the sync
      const response = await api.post<{ task_id: string }>(
        `/api/v1/connectors/${connectorId}/sync`,
        { max_files: 100 },
      );
      const taskId = response.data.task_id;
      console.log(`Sync started: ${taskId}`);

      // Connect to SSE stream for progress updates
      // Get auth token from cookies (Langflow stores it there)
      const cookies = new Cookies();
      const authToken = cookies.get(LANGFLOW_ACCESS_TOKEN) || "";

      const eventSource = new EventSource(
        `/api/v1/connectors/${connectorId}/sync/progress/${taskId}?token=${authToken}`,
      );

      eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);

        if (data.status === "done") {
          eventSource.close();
          setSyncingIds((prev) => {
            const next = new Set(prev);
            next.delete(connectorId);
            return next;
          });
          setSyncProgress((prev) => {
            const next = { ...prev };
            delete next[connectorId];
            return next;
          });
          loadConnectors(); // Reload to show updated status
        } else if (data.status === "error") {
          eventSource.close();
          console.error("Sync error:", data.message);
          setSyncingIds((prev) => {
            const next = new Set(prev);
            next.delete(connectorId);
            return next;
          });
        } else {
          // Update progress
          setSyncProgress((prev) => ({
            ...prev,
            [connectorId]: {
              progress: data.progress || 0,
              message: data.message || "Syncing...",
            },
          }));
        }
      };

      eventSource.onerror = () => {
        eventSource.close();
        setSyncingIds((prev) => {
          const next = new Set(prev);
          next.delete(connectorId);
          return next;
        });
        console.error("SSE connection error");
      };
    } catch (error) {
      console.error("Sync failed:", error);
      setSyncingIds((prev) => {
        const next = new Set(prev);
        next.delete(connectorId);
        return next;
      });
    }
  };

  // Delete connector
  const handleDelete = async (connectorId: string) => {
    if (!confirm("Are you sure you want to delete this connection?")) return;

    try {
      await api.delete(`/api/v1/connectors/${connectorId}`);
      loadConnectors();
    } catch (error) {
      console.error("Failed to delete connector:", error);
    }
  };

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin" />
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Data Connectors</h2>
          <p className="text-muted-foreground">
            Connect cloud storage to sync files to your knowledge bases
          </p>
        </div>
        <Button onClick={() => setIsDialogOpen(true)}>+ Add Connector</Button>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {connectors.length === 0 ? (
          <Card className="col-span-full">
            <CardContent className="flex flex-col items-center justify-center py-12">
              <p className="text-muted-foreground">
                No connectors yet. Click "Add Connector" to get started.
              </p>
            </CardContent>
          </Card>
        ) : (
          connectors.map((connector) => (
            <Card key={connector.id}>
              <CardHeader>
                <CardTitle className="flex items-center justify-between">
                  <span>{connector.name}</span>
                  {connector.is_authenticated ? (
                    <span className="text-xs font-normal text-green-600">
                      ✓ Connected
                    </span>
                  ) : (
                    <span className="text-xs font-normal text-yellow-600">
                      ⚠ Not authenticated
                    </span>
                  )}
                </CardTitle>
                <CardDescription>
                  {connector.connector_type === "google_drive"
                    ? "Google Drive"
                    : connector.connector_type}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-2">
                {connector.last_sync && (
                  <p className="text-sm text-muted-foreground">
                    Last sync: {new Date(connector.last_sync).toLocaleString()}
                  </p>
                )}

                {/* Show progress bar when syncing */}
                {syncProgress[connector.id] && (
                  <div className="space-y-1">
                    <div className="flex items-center justify-between text-xs">
                      <span>{syncProgress[connector.id].message}</span>
                      <span>{syncProgress[connector.id].progress}%</span>
                    </div>
                    <div className="h-2 w-full overflow-hidden rounded-full bg-secondary">
                      <div
                        className="h-full bg-primary transition-all duration-300"
                        style={{
                          width: `${syncProgress[connector.id].progress}%`,
                        }}
                      />
                    </div>
                  </div>
                )}

                <div className="flex gap-2">
                  {connector.is_authenticated ? (
                    <>
                      <Button
                        size="sm"
                        onClick={() => handleSync(connector.id)}
                        disabled={syncingIds.has(connector.id)}
                      >
                        {syncingIds.has(connector.id) ? (
                          <>
                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                            Syncing...
                          </>
                        ) : (
                          "Sync Now"
                        )}
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleDelete(connector.id)}
                      >
                        Remove
                      </Button>
                    </>
                  ) : (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={async () => {
                        // Re-authenticate
                        try {
                          const oauthResponse = await api.get<{
                            authorization_url: string;
                          }>(`/api/v1/connectors/${connector.id}/oauth/url`);
                          window.open(
                            oauthResponse.data.authorization_url,
                            "OAuth",
                            "width=600,height=700",
                          );
                        } catch (error) {
                          console.error("Failed to get OAuth URL:", error);
                        }
                      }}
                    >
                      Authenticate
                    </Button>
                  )}
                </div>
              </CardContent>
            </Card>
          ))
        )}
      </div>

      {/* Add Connector Dialog */}
      <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add Google Drive Connector</DialogTitle>
            <DialogDescription>
              Connect your Google Drive to sync files to Langflow
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div>
              <Label htmlFor="connector-name">Connection Name</Label>
              <Input
                id="connector-name"
                placeholder="e.g., My Google Drive"
                value={newConnectorName}
                onChange={(e) => setNewConnectorName(e.target.value)}
                onKeyPress={(e) => {
                  if (e.key === "Enter") handleCreateConnector();
                }}
              />
              <p className="mt-1 text-xs text-muted-foreground">
                This helps you identify this connection if you have multiple
              </p>
            </div>

            <div className="flex justify-end gap-2">
              <Button
                variant="outline"
                onClick={() => {
                  setIsDialogOpen(false);
                  setNewConnectorName("");
                }}
              >
                Cancel
              </Button>
              <Button
                onClick={handleCreateConnector}
                disabled={isCreating || !newConnectorName.trim()}
              >
                {isCreating ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Connecting...
                  </>
                ) : (
                  "Connect with Google"
                )}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
