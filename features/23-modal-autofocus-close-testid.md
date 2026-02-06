# Feature 23: Modal Autofocus Removal & Close Button TestID

## Summary

Removes the `onOpenAutoFocus` prop from the modal system (`BaseModal`, `ConfirmationModal`, `SaveChangesModal`) and adds a `data-testid="edit-button-close"` attribute to the Close button in `EditNodeModal`. The autofocus behavior was previously used to focus the "Replace" button in the `SaveChangesModal`, but this has been removed entirely to simplify modal behavior.

## Dependencies

None. This is a self-contained UI cleanup.

## Files Changed

### 1. `src/frontend/src/modals/baseModal/index.tsx` (MODIFIED)

Removes the `onOpenAutoFocus` prop from the `BaseModalProps` interface and from both `DialogContent` and `DialogContentWithouFixed` usages.

```diff
diff --git a/src/frontend/src/modals/baseModal/index.tsx b/src/frontend/src/modals/baseModal/index.tsx
index b57b42ab3c..16260140b5 100644
--- a/src/frontend/src/modals/baseModal/index.tsx
+++ b/src/frontend/src/modals/baseModal/index.tsx
@@ -217,7 +217,6 @@ interface BaseModalProps {
   type?: "modal" | "dialog" | "full-screen";
   onSubmit?: () => void;
   onEscapeKeyDown?: (e: KeyboardEvent) => void;
-  onOpenAutoFocus?: (e: Event) => void;
   closeButtonClassName?: string;
   dialogContentWithouFixed?: boolean;
 }
@@ -231,7 +230,6 @@ function BaseModal({
   type = "dialog",
   onSubmit,
   onEscapeKeyDown,
-  onOpenAutoFocus,
   closeButtonClassName,
   dialogContentWithouFixed = false,
 }: BaseModalProps) {
@@ -292,7 +290,6 @@ function BaseModal({
             <DialogContentWithouFixed
               onClick={(e) => e.stopPropagation()}
               onEscapeKeyDown={onEscapeKeyDown}
-              onOpenAutoFocus={onOpenAutoFocus}
               className={contentClasses}
               closeButtonClassName={closeButtonClassName}
             >
@@ -314,7 +311,6 @@ function BaseModal({
             <DialogContent
               onClick={(e) => e.stopPropagation()}
               onEscapeKeyDown={onEscapeKeyDown}
-              onOpenAutoFocus={onOpenAutoFocus}
               className={contentClasses}
               closeButtonClassName={closeButtonClassName}
             >
```

### 2. `src/frontend/src/modals/confirmationModal/index.tsx` (MODIFIED)

Removes the `onOpenAutoFocus` prop from the component's destructured props and from the `BaseModal` usage.

```diff
diff --git a/src/frontend/src/modals/confirmationModal/index.tsx b/src/frontend/src/modals/confirmationModal/index.tsx
index e7a510313b..b28e323678 100644
--- a/src/frontend/src/modals/confirmationModal/index.tsx
+++ b/src/frontend/src/modals/confirmationModal/index.tsx
@@ -41,7 +41,6 @@ function ConfirmationModal({
   index,
   onConfirm,
   open,
-  onOpenAutoFocus,
   onClose,
   onCancel,
   ...props
@@ -79,12 +78,7 @@ function ConfirmationModal({
   };

   return (
-    <BaseModal
-      {...props}
-      open={open}
-      setOpen={setModalOpen}
-      onOpenAutoFocus={onOpenAutoFocus}
-    >
+    <BaseModal {...props} open={open} setOpen={setModalOpen}>
       <BaseModal.Trigger>{triggerChild}</BaseModal.Trigger>
       <BaseModal.Header description={titleHeader ?? null}>
         <span className="pr-2">{title}</span>
```

### 3. `src/frontend/src/modals/saveChangesModal/index.tsx` (MODIFIED)

Removes the `handleOpenAutoFocus` callback and the `onOpenAutoFocus` prop passed to `ConfirmationModal`. Also removes the now-unused `useCallback` import.

```diff
diff --git a/src/frontend/src/modals/saveChangesModal/index.tsx b/src/frontend/src/modals/saveChangesModal/index.tsx
index de7f110638..c47923b16c 100644
--- a/src/frontend/src/modals/saveChangesModal/index.tsx
+++ b/src/frontend/src/modals/saveChangesModal/index.tsx
@@ -1,5 +1,5 @@
 import { truncate } from "lodash";
-import { useCallback, useState } from "react";
+import { useState } from "react";
 import ForwardedIconComponent from "@/components/common/genericIconComponent";
 import Loading from "@/components/ui/loading";
 import ConfirmationModal from "../confirmationModal";
@@ -20,14 +20,6 @@ export function SaveChangesModal({
   autoSave: boolean;
 }): JSX.Element {
   const [saving, setSaving] = useState(false);
-
-  const handleOpenAutoFocus = useCallback((e: Event) => {
-    e.preventDefault();
-    (
-      document.querySelector('[data-testid="replace-button"]') as HTMLElement
-    )?.focus();
-  }, []);
-
   return (
     <ConfirmationModal
       open={true}
@@ -50,7 +42,6 @@ export function SaveChangesModal({
       onCancel={onProceed}
       loading={autoSave ? true : saving}
       size="x-small"
-      onOpenAutoFocus={handleOpenAutoFocus}
     >
       <ConfirmationModal.Content>
         {autoSave ? (
```

### 4. `src/frontend/src/modals/editNodeModal/index.tsx` (MODIFIED)

Adds `data-testid="edit-button-close"` to the Close button for test automation.

```diff
diff --git a/src/frontend/src/modals/editNodeModal/index.tsx b/src/frontend/src/modals/editNodeModal/index.tsx
index c6e56d3864..cefb03fcd1 100644
--- a/src/frontend/src/modals/editNodeModal/index.tsx
+++ b/src/frontend/src/modals/editNodeModal/index.tsx
@@ -50,7 +50,12 @@ const EditNodeModal = ({
       </BaseModal.Content>
       <BaseModal.Footer>
         <div className="flex w-full justify-end gap-2 pt-2">
-          <Button onClick={() => setOpen(false)}>Close</Button>
+          <Button
+            onClick={() => setOpen(false)}
+            data-testid="edit-button-close"
+          >
+            Close
+          </Button>
         </div>
       </BaseModal.Footer>
     </BaseModal>
```

### 5. `src/frontend/src/types/components/index.ts` (MODIFIED)

Removes the `onOpenAutoFocus` property from the `ConfirmationModalType` type definition.

```diff
diff --git a/src/frontend/src/types/components/index.ts b/src/frontend/src/types/components/index.ts
index 1f0af0a6a5..c59751fb29 100644
--- a/src/frontend/src/types/components/index.ts
+++ b/src/frontend/src/types/components/index.ts
@@ -407,7 +407,6 @@ export type ConfirmationModalType = {
     | "small-h-full"
     | "medium-h-full";
   onEscapeKeyDown?: (e: KeyboardEvent) => void;
-  onOpenAutoFocus?: (e: Event) => void;
 };

 export type UserManagementType = {
```

## Implementation Notes

1. **Why remove autofocus?** The `onOpenAutoFocus` prop was only used in `SaveChangesModal` to programmatically focus the "Replace" button via a DOM query (`document.querySelector('[data-testid="replace-button"]')`). This was fragile (relies on testid existence) and arguably bad UX -- users may not want a destructive action pre-focused.

2. **Clean removal** -- The prop is removed at every layer: the type definition (`ConfirmationModalType`), the `BaseModal` interface, the `ConfirmationModal` component, and the `SaveChangesModal` consumer. No orphaned references remain.

3. **Close button testid** -- The `data-testid="edit-button-close"` addition in `EditNodeModal` enables E2E tests (likely Playwright or Cypress) to reliably target the close button.
