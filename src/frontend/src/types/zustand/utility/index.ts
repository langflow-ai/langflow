import type { EventDeliveryType } from "@/constants/enums";
import type { Pagination, Tag } from "@/types/utils/types";

export type UtilityStoreType = {
  awaitingBotResponse: boolean;
  setAwaitingBotResponse: (value: boolean) => void;
  selectedItems: string[];
  setSelectedItems: (itemId: string) => void;
  healthCheckTimeout: string | null;
  setHealthCheckTimeout: (timeout: string | null) => void;
  playgroundScrollBehaves: ScrollBehavior;
  setPlaygroundScrollBehaves: (behaves: ScrollBehavior) => void;
  maxFileSizeUpload: number;
  setMaxFileSizeUpload: (maxFileSizeUpload: number) => void;
  flowsPagination: Pagination;
  setFlowsPagination: (pagination: Pagination) => void;
  tags: Tag[];
  setTags: (tags: Tag[]) => void;
  featureFlags: Record<string, unknown>;
  setFeatureFlags: (featureFlags: Record<string, unknown>) => void;
  webhookPollingInterval: number;
  setWebhookPollingInterval: (webhookPollingInterval: number) => void;
  chatValueStore: string;
  setChatValueStore: (value: string) => void;
  currentSessionId: string;
  setCurrentSessionId: (sessionId: string) => void;
  setClientId: (clientId: string) => void;
  clientId: string;
  eventDelivery: EventDeliveryType;
  setEventDelivery: (eventDelivery: EventDeliveryType) => void;
  serializationMaxItemsLength: number;
  setSerializationMaxItemsLength: (serializationMaxItemsLength: number) => void;
  webhookAuthEnable: boolean;
  setWebhookAuthEnable: (webhookAuthEnable: boolean) => void;
  defaultFolderName: string;
  setDefaultFolderName: (defaultFolderName: string) => void;
  hideGettingStartedProgress: boolean;
  setHideGettingStartedProgress: (hideGettingStartedProgress: boolean) => void;
  allowCustomComponents: boolean;
  setAllowCustomComponents: (allowCustomComponents: boolean) => void;
  mcpBaseUrl: string;
  setMcpBaseUrl: (mcpBaseUrl: string) => void;
  /**
   * Mode A only: gates the palette Bundle-header Reload action at runtime.
   * Sourced from the backend ``/config`` response (mirrors
   * ``settings.enable_extension_reload``) so a ``langflow run`` started
   * with ``LANGFLOW_ENABLE_EXTENSION_RELOAD=true`` (or via ``--env-file``,
   * or by ``lfx extension dev``) lights up the Reload button without a
   * frontend rebuild.  The build-time Vite flag (ENABLE_EXTENSION_RELOAD)
   * still gates first paint; the UI consults BOTH so Mode B/C deployments
   * with the build flag off keep the button hidden even if a misconfigured
   * backend turns it on.
   */
  enableExtensionReload: boolean;
  setEnableExtensionReload: (enableExtensionReload: boolean) => void;
  // Embedded mode flags
  embeddedMode: boolean;
  setEmbeddedMode: (embeddedMode: boolean) => void;
  hideLogoutButton: boolean;
  setHideLogoutButton: (hideLogoutButton: boolean) => void;
  hideNewProjectButton: boolean;
  setHideNewProjectButton: (hideNewProjectButton: boolean) => void;
  hideNewFlowButton: boolean;
  setHideNewFlowButton: (hideNewFlowButton: boolean) => void;
  hideStarterProjects: boolean;
  setHideStarterProjects: (hideStarterProjects: boolean) => void;
  mcpServersLocked: boolean;
  setMcpServersLocked: (mcpServersLocked: boolean) => void;
  customComponentAdminOnly: boolean;
  setCustomComponentAdminOnly: (customComponentAdminOnly: boolean) => void;
};
