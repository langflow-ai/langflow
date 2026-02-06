# Feature 9: API Modal 2-Panel Redesign

## Summary

Redesigns the API Modal into a 2-panel layout. The main modal shows the API code tabs (Python, cURL, etc.) with a smaller "medium" size, while a secondary "Input Schema" modal (opened via a Tweaks button) allows users to configure which component fields are exposed in the API schema. Adds endpoint name editing, a `ComponentSelector` dropdown to pick components, and a `FieldSelector` to toggle individual fields on/off for API exposure. The tweaks store now supports an `api_only` flag on template fields, and the Python code generator supports a clean v2 stateless API endpoint for flows with API Response components.

## Dependencies

- `src/frontend/src/stores/tweaksStore.ts` (existing store, modified)
- `src/frontend/src/components/core/codeTabsComponent/components/tweaksComponent` (existing component, used in new layout)
- `src/frontend/src/components/ui/` (Button, Input, Label, Separator, Select UI primitives)
- `src/frontend/src/customization/components/custom-api-generator` (existing)

## File Diffs

### `src/frontend/src/modals/apiModal/components/ComponentSelector.tsx` (new)

```diff
diff --git a/src/frontend/src/modals/apiModal/components/ComponentSelector.tsx b/src/frontend/src/modals/apiModal/components/ComponentSelector.tsx
new file mode 100644
index 0000000000..bc0bbf2e2e
--- /dev/null
+++ b/src/frontend/src/modals/apiModal/components/ComponentSelector.tsx
@@ -0,0 +1,74 @@
+import IconComponent from "@/components/common/genericIconComponent";
+import { Button } from "@/components/ui/button";
+import {
+  Select,
+  SelectContent,
+  SelectItem,
+  SelectTrigger,
+  SelectValue,
+} from "@/components/ui/select";
+import { useTweaksStore } from "@/stores/tweaksStore";
+import type { AllNodeType } from "@/types/flow";
+
+interface ComponentSelectorProps {
+  selectedComponentId: string | null;
+  onComponentSelect: (componentId: string | null) => void;
+}
+
+export function ComponentSelector({
+  selectedComponentId,
+  onComponentSelect,
+}: ComponentSelectorProps) {
+  const nodes = useTweaksStore((state) => state.nodes);
+
+  // Filter out output components (ChatOutput, APIResponse, etc.)
+  const inputNodes =
+    nodes?.filter((node: AllNodeType) => {
+      const nodeType = node.data?.node?.display_name || node.data?.type;
+      return (
+        nodeType &&
+        !nodeType.endsWith("Output") &&
+        !nodeType.includes("Response")
+      );
+    }) || [];
+
+  const selectedNode = selectedComponentId
+    ? nodes?.find((node: AllNodeType) => node.data.id === selectedComponentId)
+    : null;
+
+  return (
+    <div className="flex flex-col gap-3 pr-2">
+      <Select
+        value={selectedComponentId || ""}
+        onValueChange={(value) => onComponentSelect(value || null)}
+      >
+        <SelectTrigger className="w-full h-10 border-border bg-card hover:bg-accent/50 focus:ring-0 focus:ring-offset-0">
+          <SelectValue placeholder="Select a component..." />
+        </SelectTrigger>
+        <SelectContent>
+          {inputNodes.map((node: AllNodeType) => {
+            const componentIcon = node.data?.node?.icon || node.data?.type;
+            return (
+              <SelectItem
+                key={node.data?.id || node.id}
+                value={node.data?.id || node.id}
+              >
+                <div className="flex items-center gap-2">
+                  <IconComponent name={componentIcon} className="h-4 w-4" />
+                  <span className="font-medium">
+                    {node.data?.id || node.id}
+                  </span>
+                </div>
+              </SelectItem>
+            );
+          })}
+          {inputNodes.length === 0 && (
+            <SelectItem value="" disabled>
+              No input components available
+            </SelectItem>
+          )}
+        </SelectContent>
+      </Select>
+    </div>
+  );
+}
```

### `src/frontend/src/modals/apiModal/components/FieldSelector.tsx` (new)

```diff
diff --git a/src/frontend/src/modals/apiModal/components/FieldSelector.tsx b/src/frontend/src/modals/apiModal/components/FieldSelector.tsx
new file mode 100644
index 0000000000..cc17583569
--- /dev/null
+++ b/src/frontend/src/modals/apiModal/components/FieldSelector.tsx
@@ -0,0 +1,137 @@
+import { useMemo } from "react";
+import sortFields from "@/CustomNodes/utils/sort-fields";
+import IconComponent from "@/components/common/genericIconComponent";
+import { Button } from "@/components/ui/button";
+import { useTweaksStore } from "@/stores/tweaksStore";
+import type { AllNodeType } from "@/types/flow";
+
+interface FieldSelectorProps {
+  componentId: string;
+}
+
+export function FieldSelector({ componentId }: FieldSelectorProps) {
+  const nodes = useTweaksStore((state) => state.nodes);
+  const setNode = useTweaksStore((state) => state.setNode);
+
+  const selectedNode = useMemo(() => {
+    return nodes?.find((node: AllNodeType) => node.data.id === componentId);
+  }, [nodes, componentId]);
+
+  const availableFields = useMemo(() => {
+    if (!selectedNode?.data?.node?.template) return [];
+
+    return Object.keys(selectedNode.data.node.template)
+      .filter((key: string) => {
+        const templateParam = selectedNode.data.node!.template[key] as any;
+        return (
+          key.charAt(0) !== "_" &&
+          templateParam.show &&
+          !(
+            (key === "code" && templateParam.type === "code") ||
+            (key.includes("code") && templateParam.proxy)
+          )
+        );
+      })
+      .sort((a, b) =>
+        sortFields(a, b, selectedNode.data.node!.field_order ?? []),
+      )
+      .map((key: string) => {
+        const templateParam = selectedNode.data.node!.template[key] as any;
+        return {
+          key,
+          name: templateParam.name || key,
+          display_name: templateParam.display_name || templateParam.name || key,
+          description: templateParam.info || templateParam.description || "",
+        };
+      });
+  }, [selectedNode]);
+
+  const handleFieldToggle = (fieldKey: string) => {
+    if (!selectedNode) return;
+
+    const fieldTemplate = selectedNode.data.node!.template[fieldKey];
+    const isCurrentlySelected = !fieldTemplate.advanced;
+
+    // Create updated node with field toggle
+    const updatedNode = {
+      ...selectedNode,
+      data: {
+        ...selectedNode.data,
+        node: {
+          ...selectedNode.data.node!,
+          template: {
+            ...selectedNode.data.node!.template,
+            [fieldKey]: {
+              ...fieldTemplate,
+              // Toggle advanced flag to control inclusion in tweaks
+              advanced: isCurrentlySelected,
+              // Keep the original value
+              value: fieldTemplate.value || "",
+            },
+          },
+        },
+      },
+    };
+
+    // Update the node which will trigger updateTweaks
+    setNode(componentId, updatedNode);
+  };
+
+  const isFieldSelected = (fieldKey: string) => {
+    if (!selectedNode) return false;
+    const fieldTemplate = selectedNode.data.node!.template[fieldKey];
+    // Field is selected if it's not marked as advanced (which means it's included in tweaks)
+    return !fieldTemplate.advanced;
+  };
+
+  if (!selectedNode) {
+    return null;
+  }
+
+  const componentDisplayName =
+    selectedNode?.data.node?.display_name || selectedNode?.data.id || "";
+
+  return (
+    <div className="flex flex-col gap-3">
+      <div className="space-y-2 pr-2">
+        {availableFields.map((field) => {
+          const isSelected = isFieldSelected(field.key);
+
+          return (
+            <Button
+              key={field.key}
+              variant="ghost"
+              className={`flex h-auto w-full justify-start gap-3 p-3 text-left border rounded-lg ${
+                isSelected
+                  ? "bg-accent border-accent-foreground/20"
+                  : "bg-muted/50 border-border/50 hover:bg-muted/80"
+              }`}
+              onClick={() => handleFieldToggle(field.key)}
+            >
+              <div className="flex min-w-0 flex-1 flex-col gap-1">
+                <div className="font-medium truncate">{field.display_name}</div>
+                {field.description && (
+                  <div className="text-xs text-muted-foreground line-clamp-2 overflow-hidden text-ellipsis">
+                    {field.description}
+                  </div>
+                )}
+              </div>
+              {isSelected && (
+                <IconComponent
+                  name="Check"
+                  className="h-4 w-4 text-accent-foreground"
+                />
+              )}
+            </Button>
+          );
+        })}
+
+        {availableFields.length === 0 && (
+          <div className="flex h-32 items-center justify-center text-sm text-muted-foreground">
+            No configurable fields available for this component
+          </div>
+        )}
+      </div>
+    </div>
+  );
+}
```

### `src/frontend/src/modals/apiModal/utils/get-python-api-code.tsx` (modified)

```diff
diff --git a/src/frontend/src/modals/apiModal/utils/get-python-api-code.tsx b/src/frontend/src/modals/apiModal/utils/get-python-api-code.tsx
index 08bac75ff8..f041bf4a54 100644
--- a/src/frontend/src/modals/apiModal/utils/get-python-api-code.tsx
+++ b/src/frontend/src/modals/apiModal/utils/get-python-api-code.tsx
@@ -15,11 +15,13 @@ export function getNewPythonApiCode({
   endpointName,
   processedPayload,
   shouldDisplayApiKey,
+  hasAPIResponse = false,
 }: {
   flowId: string;
   endpointName: string;
   processedPayload: any;
   shouldDisplayApiKey: boolean;
+  hasAPIResponse?: boolean;
 }): string {
   const baseUrl = getBaseUrl();

@@ -29,7 +31,10 @@ export function getNewPythonApiCode({

   // If no file uploads, use existing logic
   if (!hasFiles) {
-    const apiUrl = `${baseUrl}/api/v1/run/${endpointName || flowId}`;
+    const apiUrl = hasAPIResponse
+      ? `${baseUrl}/api/v2/run/stateless/${endpointName || flowId}`
+      : `${baseUrl}/api/v1/run/${endpointName || flowId}`;
+
     const payloadString = JSON.stringify(processedPayload, null, 4)
       .replace(/true/g, "True")
       .replace(/false/g, "False")
@@ -43,7 +48,34 @@ export function getNewPythonApiCode({
       ? `headers = {"x-api-key": api_key}`
       : getApiSampleHeaders("python");

-    return `import requests
+    if (hasAPIResponse) {
+      // Clean workflow API for API Response components - only send tweaks
+      const workflowPayload = processedPayload.tweaks
+        ? { tweaks: processedPayload.tweaks }
+        : {};
+      const workflowPayloadString = JSON.stringify(workflowPayload, null, 4)
+        .replace(/true/g, "True")
+        .replace(/false/g, "False")
+        .replace(/null/g, "None");
+
+      return `import requests
+
+${authSection}url = "${apiUrl}"  # Clean workflow API endpoint
+
+# Request payload configuration (only tweaks for workflow API)
+payload = ${workflowPayloadString}
+${headersSection}
+# Send API request
+response = requests.post(url, json=payload${shouldDisplayApiKey ? ", headers=headers" : ""})
+response.raise_for_status()  # Raise exception for bad status codes
+
+# Parse clean JSON response
+result = response.json()
+print("Output:", result["output"])
+print("Metadata:", result["metadata"])`;
+    } else {
+      // Original chat/text API with session management
+      return `import requests
 import os
 import uuid

@@ -68,6 +100,7 @@ except requests.exceptions.RequestException as e:
     print(f"Error making API request: {e}")
 except ValueError as e:
     print(f"Error parsing response: {e}")`;
+    }
   }

   // File upload logic - handle multiple file types additively
```

### `src/frontend/src/modals/apiModal/index.tsx` (modified - unstaged changes)

```diff
diff --git a/src/frontend/src/modals/apiModal/index.tsx b/src/frontend/src/modals/apiModal/index.tsx
index 566b1b6a20..b8c6076067 100644
--- a/src/frontend/src/modals/apiModal/index.tsx
+++ b/src/frontend/src/modals/apiModal/index.tsx
@@ -1,18 +1,30 @@
+import { TweaksComponent } from "@/components/core/codeTabsComponent/components/tweaksComponent";
 import { Button } from "@/components/ui/button";
+import { Input } from "@/components/ui/input";
+import { Label } from "@/components/ui/label";
+import { Separator } from "@/components/ui/separator";
 import { CustomAPIGenerator } from "@/customization/components/custom-api-generator";
 import { CustomLink } from "@/customization/components/custom-link";
+import useSaveFlow from "@/hooks/flows/use-save-flow";
+import useAuthStore from "@/stores/authStore";
 import useFlowStore from "@/stores/flowStore";
+import useFlowsManagerStore from "@/stores/flowsManagerStore";
+import { isEndpointNameValid } from "@/utils/utils";
 import "ace-builds/src-noconflict/ext-language_tools";
 import "ace-builds/src-noconflict/mode-python";
 import "ace-builds/src-noconflict/theme-github";
 import "ace-builds/src-noconflict/theme-twilight";
-import { type ReactNode, useEffect, useState } from "react";
+import { cloneDeep } from "lodash";
+import { type ChangeEvent, type ReactNode, useEffect, useState } from "react";
 import { useShallow } from "zustand/react/shallow";
 import IconComponent from "../../components/common/genericIconComponent";
 import { useTweaksStore } from "../../stores/tweaksStore";
 import BaseModal from "../baseModal";
 import APITabsComponent from "./codeTabs/code-tabs";

+const MAX_LENGTH = 20;
+const MIN_LENGTH = 1;
+
 export default function ApiModal({
   children,
   open: myOpen,
@@ -22,60 +34,181 @@ export default function ApiModal({
   open?: boolean;
   setOpen?: (a: boolean | ((o?: boolean) => boolean)) => void;
 }) {
+  const _autoLogin = useAuthStore((state) => state.autoLogin);
   const nodes = useFlowStore((state) => state.nodes);
+  const [openTweaks, setOpenTweaks] = useState(false);
+  const tweaks = useTweaksStore((state) => state.tweaks);
   const [open, setOpen] =
     mySetOpen !== undefined && myOpen !== undefined
       ? [myOpen, mySetOpen]
       : useState(false);
   const initialSetup = useTweaksStore((state) => state.initialSetup);

+  const flowEndpointName = useFlowStore(
+    useShallow((state) => state.currentFlow?.endpoint_name),
+  );
+
   const currentFlowId = useFlowStore(
     useShallow((state) => state.currentFlow?.id),
   );

+  const [endpointName, setEndpointName] = useState(flowEndpointName ?? "");
+  const [validEndpointName, setValidEndpointName] = useState(true);
+
+  const handleEndpointNameChange = (event: ChangeEvent<HTMLInputElement>) => {
+    const { value } = event.target;
+    // Validate the endpoint name
+    // use this regex r'^[a-zA-Z0-9_-]+$'
+    const isValid = isEndpointNameValid(event.target.value, MAX_LENGTH);
+    setValidEndpointName(isValid);
+
+    // Only update if valid and meets minimum length (if set)
+    if (isValid && value.length >= MIN_LENGTH) {
+      setEndpointName!(value);
+    } else if (value.length === 0) {
+      // Always allow empty endpoint name (it's optional)
+      setEndpointName!("");
+    }
+  };
+
   useEffect(() => {
     if (open && currentFlowId) initialSetup(nodes, currentFlowId);
   }, [open]);

+  const autoSaving = useFlowsManagerStore((state) => state.autoSaving);
+  const saveFlow = useSaveFlow();
+  const setCurrentFlow = useFlowStore((state) => state.setCurrentFlow);
+
+  function handleSave(): void {
+    const newFlow = cloneDeep(useFlowStore.getState().currentFlow);
+    if (!newFlow) return;
+    newFlow.endpoint_name =
+      endpointName && endpointName.length > 0 ? endpointName : null;
+
+    if (autoSaving) {
+      saveFlow(newFlow);
+    } else {
+      setCurrentFlow(newFlow);
+    }
+  }
+
+  useEffect(() => {
+    if (!openTweaks && endpointName !== flowEndpointName) handleSave();
+    else if (openTweaks) {
+      setEndpointName(flowEndpointName ?? "");
+    }
+  }, [openTweaks]);
+
   return (
-    <BaseModal
-      closeButtonClassName="!top-3"
-      open={open}
-      setOpen={setOpen}
-      size="x-large"
-      className="pt-4"
-    >
-      <BaseModal.Trigger asChild>{children}</BaseModal.Trigger>
-      <BaseModal.Header
-        description={
-          <span className="pr-2">
-            API access requires an API key. You can{" "}
-            <CustomLink
-              to="/settings/api-keys"
-              className="text-accent-pink-foreground"
-            >
-              {" "}
-              create an API key
-            </CustomLink>{" "}
-            in settings.
-          </span>
-        }
+    <>
+      <BaseModal
+        closeButtonClassName="!top-3"
+        open={open}
+        setOpen={setOpen}
+        size="medium"
+        className="pt-4"
+      >
+        <BaseModal.Trigger asChild>{children}</BaseModal.Trigger>
+        <BaseModal.Header
+          description={
+            <span className="pr-2">
+              API access requires an API key. You can{" "}
+              <CustomLink
+                to="/settings/api-keys"
+                className="text-accent-pink-foreground"
+              >
+                {" "}
+                create an API key
+              </CustomLink>{" "}
+              in settings.
+            </span>
+          }
+        >
+          <IconComponent
+            name="Code2"
+            className="h-6 w-6 text-gray-800 dark:text-white"
+            aria-hidden="true"
+          />
+          <span className="pl-2">API access</span>
+          {nodes.length > 0 && (
+            <div className="border-r-1 absolute right-12 flex items-center text-mmd font-medium leading-[16px]">
+              <Button
+                variant="ghost"
+                size="icon"
+                className="h-8 select-none px-3"
+                onClick={() => setOpenTweaks(true)}
+                data-testid="tweaks-button"
+              >
+                <IconComponent
+                  name="SlidersHorizontal"
+                  className="h-3.5 w-3.5"
+                />
+                <span>Input Schema ({Object.keys(tweaks)?.length}) </span>
+              </Button>
+              <Separator orientation="vertical" className="ml-2 h-8" />
+            </div>
+          )}
+        </BaseModal.Header>
+        <BaseModal.Content overflowHidden>
+          {open && (
+            <>
+              <CustomAPIGenerator isOpen={open} />
+              <APITabsComponent />
+            </>
+          )}
+        </BaseModal.Content>
+      </BaseModal>
+
+      <BaseModal
+        open={openTweaks}
+        setOpen={setOpenTweaks}
+        size="medium-small-tall"
       >
-        <IconComponent
-          name="Code2"
-          className="h-6 w-6 text-gray-800 dark:text-white"
-          aria-hidden="true"
-        />
-        <span className="pl-2">API access</span>
-      </BaseModal.Header>
-      <BaseModal.Content overflowHidden>
-        {open && (
-          <>
-            <CustomAPIGenerator isOpen={open} />
-            <APITabsComponent />
-          </>
-        )}
-      </BaseModal.Content>
-    </BaseModal>
+        <BaseModal.Header>
+          <IconComponent name="SlidersHorizontal" className="text-f h-6 w-6" />
+          <span className="pl-2">Input Schema</span>
+        </BaseModal.Header>
+        <BaseModal.Content overflowHidden className="flex flex-col gap-4">
+          {true && (
+            <Label>
+              <div className="edit-flow-arrangement mt-2">
+                <span className="shrink-0 text-mmd font-medium">
+                  Endpoint Name
+                </span>
+                {!validEndpointName && (
+                  <span className="edit-flow-span">
+                    Use only letters, numbers, hyphens, and underscores (
+                    {MAX_LENGTH} characters max).
+                  </span>
+                )}
+              </div>
+              <Input
+                className="nopan nodelete nodrag noflow mt-2 font-normal"
+                onChange={handleEndpointNameChange}
+                type="text"
+                name="endpoint_name"
+                value={endpointName ?? ""}
+                placeholder="An alternative name to run the endpoint"
+                maxLength={MAX_LENGTH}
+                minLength={MIN_LENGTH}
+                id="endpoint_name"
+              />
+            </Label>
+          )}
+          <div className="flex flex-1 flex-col gap-2 overflow-hidden">
+            <div className="flex flex-col gap-1">
+              <span className="shrink-0 text-sm font-medium">Expose API</span>
+              <span className="text-mmd text-muted-foreground">
+                Select which component fields to expose as inputs in this flow's
+                API schema.
+              </span>
+            </div>
+            <div className="min-h-0 w-full flex-1 flex-col overflow-y-auto overflow-x-hidden rounded-lg bg-muted custom-scroll">
+              <TweaksComponent open={openTweaks} />
+            </div>
+          </div>
+        </BaseModal.Content>
+      </BaseModal>
+    </>
   );
 }
```

### `src/frontend/src/stores/tweaksStore.ts` (modified)

```diff
diff --git a/src/frontend/src/stores/tweaksStore.ts b/src/frontend/src/stores/tweaksStore.ts
index cb1af1f57f..d60c98a542 100644
--- a/src/frontend/src/stores/tweaksStore.ts
+++ b/src/frontend/src/stores/tweaksStore.ts
@@ -59,7 +59,10 @@ export const useTweaksStore = create<TweaksStoreType>((set, get) => ({
       if (nodeTemplate && node.type === "genericNode") {
         const currentTweak = {};
         Object.keys(nodeTemplate).forEach((name) => {
-          if (!nodeTemplate[name].advanced) {
+          // If api_only is explicitly set, use it; otherwise default to visible fields (not advanced)
+          const isExposedToApi =
+            nodeTemplate[name].api_only ?? !nodeTemplate[name].advanced;
+          if (isExposedToApi) {
             currentTweak[name] = getChangesType(
               nodeTemplate[name].value,
               nodeTemplate[name],
```

## Implementation Notes

1. **2-Panel Layout**: The original single `x-large` modal is replaced with a `medium`-sized modal for code display, plus a secondary `medium-small-tall` modal for the "Input Schema" tweaks panel.

2. **Input Schema Button**: A new "Input Schema (N)" button appears in the API modal header, showing the count of active tweaks. Clicking it opens the secondary tweaks modal.

3. **Endpoint Name Editing**: The tweaks panel includes an endpoint name input with validation (alphanumeric, hyphens, underscores, max 20 chars). Changes auto-save when the tweaks panel closes.

4. **API v2 Stateless Endpoint**: When the flow contains an `APIResponse` component (`hasAPIResponse` flag), the generated Python code targets `/api/v2/run/stateless/` instead of `/api/v1/run/`, with a cleaner payload (only tweaks, no session management).

5. **`api_only` Flag**: The tweaks store now checks for an `api_only` property on template fields before falling back to the `!advanced` check, giving finer control over which fields appear in the API schema.

6. **ComponentSelector and FieldSelector**: These new sub-components were created for a more granular field-level selection UI, though the main modal currently uses the existing `TweaksComponent` for the accordion-based tweaks display.
