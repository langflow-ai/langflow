# Feature 27: Miscellaneous UI Tweaks

## Summary

A collection of small UI refinements:

1. **Loading component redesign** -- Replaces the generic spinner SVG with an animated Langflow logo that draws itself with stroke animations, then fills in.
2. **App header spacing tweaks** -- Reduces gaps and padding in the header's right section (GitHub/Discord counts, notification bell, separator) for a tighter layout.
3. **New SVG loading assets** -- Two new SVG files for the branded loading animation.
4. **Stable hash history updates** -- Hash changes for `File`, `KnowledgeIngestion`, `KnowledgeRetrieval`, `SaveToFile` components, plus new entries for `ProgressTest` and `CombineInputs`.
5. **Component index** -- Large regenerated JSON file (needs `make build_component_index` to rebuild).

## Dependencies

None. These are purely cosmetic/asset changes.

## Files Changed

### 1. `src/frontend/src/components/common/loadingComponent/index.tsx` (MODIFIED)

Complete overhaul of the loading spinner. Replaces the circular spinner with an animated SVG of the Langflow logo using CSS `@keyframes` for sequential stroke drawing and fill-in effects.

```diff
diff --git a/src/frontend/src/components/common/loadingComponent/index.tsx b/src/frontend/src/components/common/loadingComponent/index.tsx
index f3e63c8741..f1b51a77a5 100644
--- a/src/frontend/src/components/common/loadingComponent/index.tsx
+++ b/src/frontend/src/components/common/loadingComponent/index.tsx
@@ -7,22 +7,79 @@ export default function LoadingComponent({
     <div role="status" className="flex flex-col items-center justify-center">
       <svg
         aria-hidden="true"
-        className={`w-${remSize} h-${remSize} animate-spin fill-primary text-muted`}
-        viewBox="0 0 100 101"
+        className="text-primary"
+        style={{ width: `${remSize * 2}px`, height: `${remSize * 2}px` }}
+        viewBox="0 0 470 470"
         fill="none"
         xmlns="http://www.w3.org/2000/svg"
       >
+        <style>
+          {`
+            @keyframes drawTop {
+              0% { stroke-dashoffset: 1000; }
+              25%, 100% { stroke-dashoffset: 0; }
+            }
+            @keyframes drawMiddle {
+              0%, 25% { stroke-dashoffset: 1000; }
+              50%, 100% { stroke-dashoffset: 0; }
+            }
+            @keyframes drawBottom {
+              0%, 50% { stroke-dashoffset: 1000; }
+              75%, 100% { stroke-dashoffset: 0; }
+            }
+            @keyframes fillIn {
+              0%, 75% { opacity: 0; }
+              80%, 100% { opacity: 1; }
+            }
+            .lf-line {
+              fill: none;
+              stroke: currentColor;
+              stroke-width: 12;
+              stroke-linecap: round;
+              stroke-linejoin: round;
+              stroke-dasharray: 1000;
+            }
+            .lf-fill {
+              fill: currentColor;
+              opacity: 0;
+              animation: fillIn 5s ease-in-out infinite;
+            }
+            .lf-line1 { animation: drawBottom 5s ease-in-out infinite; }
+            .lf-line2 { animation: drawTop 5s ease-in-out infinite; }
+            .lf-line3 { animation: drawMiddle 5s ease-in-out infinite; }
+          `}
+        </style>
+        {/* Filled paths (appear after outline is complete) */}
         <path
-          d="M100 50.5908C100 78.2051 77.6142 100.591 50 100.591C22.3858 100.591 0 78.2051 0 50.5908C0 22.9766 22.3858 0.59082 50 0.59082C77.6142 0.59082 100 22.9766 100 50.5908ZM9.08144 50.5908C9.08144 73.1895 27.4013 91.5094 50 91.5094C72.5987 91.5094 90.9186 73.1895 90.9186 50.5908C90.9186 27.9921 72.5987 9.67226 50 9.67226C27.4013 9.67226 9.08144 27.9921 9.08144 50.5908Z"
-          fill="currentColor"
+          className="lf-fill"
+          d="M342.604 243.34H389.75C398.998 243.34 406.489 250.831 406.489 260.079V287.892C406.489 297.14 398.998 304.631 389.75 304.631H348.629C344.186 304.631 339.928 306.4 336.787 309.54L266.225 380.091C263.084 383.232 258.827 385 254.383 385H220.463C211.39 385 203.956 377.765 203.724 368.691L202.991 340.297C202.747 330.886 210.308 323.115 219.73 323.115H248.927C253.371 323.115 257.629 321.347 260.769 318.206L330.739 248.237C333.879 245.097 338.137 243.328 342.58 243.328L342.604 243.34Z"
         />
         <path
-          d="M93.9676 39.0409C96.393 38.4038 97.8624 35.9116 97.0079 33.5539C95.2932 28.8227 92.871 24.3692 89.8167 20.348C85.8452 15.1192 80.8826 10.7238 75.2124 7.41289C69.5422 4.10194 63.2754 1.94025 56.7698 1.05124C51.7666 0.367541 46.6976 0.446843 41.7345 1.27873C39.2613 1.69328 37.813 4.19778 38.4501 6.62326C39.0873 9.04874 41.5694 10.4717 44.0505 10.1071C47.8511 9.54855 51.7191 9.52689 55.5402 10.0491C60.8642 10.7766 65.9928 12.5457 70.6331 15.2552C75.2735 17.9648 79.3347 21.5619 82.5849 25.841C84.9175 28.9121 86.7997 32.2913 88.1811 35.8758C89.083 38.2158 91.5421 39.6781 93.9676 39.0409Z"
-          fill="currentFill"
+          className="lf-fill"
+          d="M202.619 85H249.765C259.013 85 266.504 92.4913 266.504 101.739V129.552C266.504 138.8 259.013 146.291 249.765 146.291H208.644C204.201 146.291 199.943 148.06 196.802 151.2L126.24 221.763C123.099 224.904 118.842 226.672 114.398 226.672H80.4777C71.4044 226.672 63.9712 219.436 63.7386 210.363L63.0058 181.968C62.7615 172.558 70.3226 164.799 79.7449 164.799H108.942C113.386 164.799 117.643 163.031 120.784 159.89L190.753 89.9205C193.894 86.7798 198.152 85.0116 202.595 85.0116L202.619 85Z"
+        />
+        <path
+          className="lf-fill"
+          d="M342.603 120.829H389.75C398.997 120.829 406.489 128.32 406.489 137.568V165.381C406.489 174.629 398.997 182.12 389.75 182.12H348.629C344.185 182.12 339.928 183.888 336.787 187.029L266.225 257.591C263.084 260.732 258.826 262.5 254.383 262.5H213.169C208.853 262.5 204.701 264.164 201.583 267.153L122.366 343.067C119.248 346.056 115.096 347.72 110.78 347.72H81.9083C72.6605 347.72 65.1692 340.217 65.1692 330.981V302.4C65.1692 293.152 72.6605 285.661 81.9083 285.661H110.571C115.014 285.661 119.272 283.892 122.413 280.752L197.64 205.525C200.78 202.384 205.038 200.616 209.481 200.616H248.927C253.371 200.616 257.628 198.848 260.769 195.707L330.738 125.738C333.879 122.597 338.136 120.829 342.58 120.829H342.603Z"
+        />
+        {/* Outlined paths (draw animation) */}
+        {/* Bottom path */}
+        <path
+          className="lf-line lf-line1"
+          d="M342.604 243.34H389.75C398.998 243.34 406.489 250.831 406.489 260.079V287.892C406.489 297.14 398.998 304.631 389.75 304.631H348.629C344.186 304.631 339.928 306.4 336.787 309.54L266.225 380.091C263.084 383.232 258.827 385 254.383 385H220.463C211.39 385 203.956 377.765 203.724 368.691L202.991 340.297C202.747 330.886 210.308 323.115 219.73 323.115H248.927C253.371 323.115 257.629 321.347 260.769 318.206L330.739 248.237C333.879 245.097 338.137 243.328 342.58 243.328L342.604 243.34Z"
+        />
+        {/* Top path */}
+        <path
+          className="lf-line lf-line2"
+          d="M202.619 85H249.765C259.013 85 266.504 92.4913 266.504 101.739V129.552C266.504 138.8 259.013 146.291 249.765 146.291H208.644C204.201 146.291 199.943 148.06 196.802 151.2L126.24 221.763C123.099 224.904 118.842 226.672 114.398 226.672H80.4777C71.4044 226.672 63.9712 219.436 63.7386 210.363L63.0058 181.968C62.7615 172.558 70.3226 164.799 79.7449 164.799H108.942C113.386 164.799 117.643 163.031 120.784 159.89L190.753 89.9205C193.894 86.7798 198.152 85.0116 202.595 85.0116L202.619 85Z"
+        />
+        {/* Middle path (longest) */}
+        <path
+          className="lf-line lf-line3"
+          d="M342.603 120.829H389.75C398.997 120.829 406.489 128.32 406.489 137.568V165.381C406.489 174.629 398.997 182.12 389.75 182.12H348.629C344.185 182.12 339.928 183.888 336.787 187.029L266.225 257.591C263.084 260.732 258.826 262.5 254.383 262.5H213.169C208.853 262.5 204.701 264.164 201.583 267.153L122.366 343.067C119.248 346.056 115.096 347.72 110.78 347.72H81.9083C72.6605 347.72 65.1692 340.217 65.1692 330.981V302.4C65.1692 293.152 72.6605 285.661 81.9083 285.661H110.571C115.014 285.661 119.272 283.892 122.413 280.752L197.64 205.525C200.78 202.384 205.038 200.616 209.481 200.616H248.927C253.371 200.616 257.628 198.848 260.769 195.707L330.738 125.738C333.879 122.597 338.136 120.829 342.58 120.829H342.603Z"
         />
       </svg>
-      <br></br>
-      <span className="animate-pulse text-lg text-primary">Loading...</span>
+      <span className="mt-4 animate-pulse text-lg text-primary">Loading...</span>
     </div>
   );
 }
```

### 2. `src/frontend/src/components/core/appHeaderComponent/index.tsx` (MODIFIED)

Adjusts spacing in the header right section: `gap-3` to `gap-1`, removes `pr-2`, reduces `px-2` to `px-1`, adds `mx-2` to separator.

```diff
diff --git a/src/frontend/src/components/core/appHeaderComponent/index.tsx b/src/frontend/src/components/core/appHeaderComponent/index.tsx
index aa5cac082b..27b00c0e03 100644
--- a/src/frontend/src/components/core/appHeaderComponent/index.tsx
+++ b/src/frontend/src/components/core/appHeaderComponent/index.tsx
@@ -77,12 +77,12 @@ export default function AppHeader(): JSX.Element {

       {/* Right Section */}
       <div
-        className={`relative left-3 z-30 flex shrink-0 items-center gap-3`}
+        className={`relative left-3 z-30 flex shrink-0 items-center gap-1`}
         data-testid="header_right_section_wrapper"
       >
         {false && <ModelProviderCount />}
         {LANGFLOW_AGENTIC_EXPERIENCE && <AssistantButton type="header" />}
-        <div className="hidden pr-2 whitespace-nowrap lg:inline-flex lg:items-center">
+        <div className="hidden whitespace-nowrap lg:inline-flex lg:items-center">
           <CustomLangflowCounts />
         </div>
         <AlertDropdown
@@ -105,7 +105,7 @@ export default function AppHeader(): JSX.Element {
                 }
                 data-testid="notification_button"
               >
-                <div className="hit-area-hover group relative items-center rounded-md px-2 py-2 text-muted-foreground">
+                <div className="hit-area-hover group relative items-center rounded-md px-1 py-2 text-muted-foreground">
                   <span className={getNotificationBadge()} />
                   <ForwardedIconComponent
                     name="Bell"
@@ -126,7 +126,7 @@ export default function AppHeader(): JSX.Element {
         </AlertDropdown>
         <Separator
           orientation="vertical"
-          className="my-auto h-7 dark:border-zinc-700"
+          className="mx-2 my-auto h-7 dark:border-zinc-700"
         />

         <div className="flex">
```

### 3. `src/frontend/src/components/core/appHeaderComponent/components/langflow-counts.tsx` (MODIFIED)

Reduces horizontal spacing in the GitHub/Discord count buttons: outer `gap-3` to `gap-1`, inner `px-2` to `px-1`.

```diff
diff --git a/src/frontend/src/components/core/appHeaderComponent/components/langflow-counts.tsx b/src/frontend/src/components/core/appHeaderComponent/components/langflow-counts.tsx
index 4421c8475d..5f75669965 100644
--- a/src/frontend/src/components/core/appHeaderComponent/components/langflow-counts.tsx
+++ b/src/frontend/src/components/core/appHeaderComponent/components/langflow-counts.tsx
@@ -14,7 +14,7 @@ export const LangflowCounts = () => {
   const formattedDiscordCount = formatNumber(discordCount);

   return (
-    <div className="flex items-center gap-3">
+    <div className="flex items-center gap-1">
       <ShadTooltip
         content="Go to GitHub repo"
         side="bottom"
@@ -25,7 +25,7 @@ export const LangflowCounts = () => {
           onClick={() => window.open(GITHUB_URL, "_blank")}
           className="hit-area-hover flex items-center gap-2 rounded-md p-1 text-muted-foreground"
         >
-          <div className="relative items-center rounded-md px-2 py-1 flex">
+          <div className="relative items-center rounded-md px-1 py-1 flex">
             <FaGithub className="h-4 w-4" />
             <Case condition={Boolean(formattedStars) && formattedStars !== "0"}>
               <span className="text-xs font-semibold pl-2">
@@ -46,7 +46,7 @@ export const LangflowCounts = () => {
           onClick={() => window.open(DISCORD_URL, "_blank")}
           className="hit-area-hover flex items-center gap-2 rounded-md p-1 text-muted-foreground"
         >
-          <div className="relative items-center rounded-md px-2 py-1 flex">
+          <div className="relative items-center rounded-md px-1 py-1 flex">
             <FaDiscord className="h-4 w-4" />
             <Case
               condition={
```

### 4. `src/lfx/src/lfx/_assets/component_index.json` (MODIFIED)

**Note:** This file is 554 lines of diff (large generated JSON). It should be rebuilt via `make build_component_index`. The diff is not included here due to its size -- it is a regenerated index of all components and their metadata.

### 5. `src/lfx/src/lfx/_assets/stable_hash_history.json` (MODIFIED)

Updated hash values for four existing components and added two new component entries.

```diff
diff --git a/src/lfx/src/lfx/_assets/stable_hash_history.json b/src/lfx/src/lfx/_assets/stable_hash_history.json
index 53b1820032..ebe06dbac6 100644
--- a/src/lfx/src/lfx/_assets/stable_hash_history.json
+++ b/src/lfx/src/lfx/_assets/stable_hash_history.json
@@ -766,22 +766,22 @@
   },
   "File": {
     "versions": {
-      "0.3.0": "12a5841f1a03"
+      "0.3.0": "fccb3ab047f1"
     }
   },
   "KnowledgeIngestion": {
     "versions": {
-      "0.3.0": "52a451e4f053"
+      "0.3.0": "d70806d0794a"
     }
   },
   "KnowledgeRetrieval": {
     "versions": {
-      "0.3.0": "af0a162c3f80"
+      "0.3.0": "a02accf0e07f"
     }
   },
   "SaveToFile": {
     "versions": {
-      "0.3.0": "6d0e4842271e"
+      "0.3.0": "6657b458359b"
     }
   },
   "FirecrawlCrawlApi": {
@@ -1773,5 +1773,15 @@
     "versions": {
       "0.3.0": "ec825c33caf6"
     }
+  },
+  "ProgressTest": {
+    "versions": {
+      "0.3.0": "48a384dd6fbb"
+    }
+  },
+  "CombineInputs": {
+    "versions": {
+      "0.3.0": "59971c95febc"
+    }
   }
 }
\ No newline at end of file
```

### 6. New SVG Assets

Two new SVG files were added as binary assets (git shows them as binary diffs):

- `src/frontend/src/assets/langflow-loading-draw.svg` (NEW, binary)
- `src/frontend/src/assets/langflow-loading.svg` (NEW, binary)

```diff
diff --git a/src/frontend/src/assets/langflow-loading-draw.svg b/src/frontend/src/assets/langflow-loading-draw.svg
new file mode 100644
index 0000000000..2ebe7c451e
Binary files /dev/null and b/src/frontend/src/assets/langflow-loading-draw.svg differ
```

```diff
diff --git a/src/frontend/src/assets/langflow-loading.svg b/src/frontend/src/assets/langflow-loading.svg
new file mode 100644
index 0000000000..9f20a81ce4
Binary files /dev/null and b/src/frontend/src/assets/langflow-loading.svg differ
```

## Implementation Notes

1. **Loading animation** -- The new loading component uses CSS `@keyframes` with `stroke-dashoffset` to create a sequential drawing effect across three paths (bottom, top, middle) of the Langflow logo. After the strokes complete (75% of the 5s cycle), the filled versions fade in (`fillIn` animation). The animation loops infinitely with `ease-in-out` timing.

2. **Size calculation** -- The old spinner used Tailwind classes (`w-${remSize} h-${remSize}`), which only works for predefined Tailwind values. The new version uses inline `style` with `${remSize * 2}px` for arbitrary sizing.

3. **Header spacing** -- All spacing reductions are from `gap-3`/`px-2` down to `gap-1`/`px-1`, creating a more compact header layout. The separator gains `mx-2` to compensate for the reduced gap.

4. **Stable hash changes** -- The hash updates for `File`, `KnowledgeIngestion`, `KnowledgeRetrieval`, and `SaveToFile` indicate these components were modified (their interfaces/implementations changed). `ProgressTest` and `CombineInputs` are entirely new components.

5. **Component index** -- The `component_index.json` is a large auto-generated file. After any component changes, it should be rebuilt with `make build_component_index`.
