---
title: Contribute bundles
slug: /contributing-bundles
---

Follow these steps to add new component bundles to the Langflow sidebar.

This example adds a new bundle named `DarthVader`.

## Add the bundle to the backend folder

1. Navigate to the backend directory in the Langflow repository and create a new folder for your bundle.
The path for your new component is `src > backend > base > langflow > components > darth_vader`.
You can view the [components folder](https://github.com/langflow-ai/langflow/tree/main/src/backend/base/langflow/components) in the Langflow repository.

2. Within the newly created `darth_vader` folder, add the following files:

* `darth_vader_component.py` — This file contains the backend logic for the new bundle. Create multiple `.py` files for multiple components.
* `__init__.py` — This file initializes the bundle components. You can use any existing `__init__.py` as an example to see how it should be structured.

For an example of adding multiple components in a bundle, see the [Notion](https://github.com/langflow-ai/langflow/tree/main/src/backend/base/langflow/components/Notion) bundle.


## Add the bundle to the frontend folder

1. Navigate to the frontend directory in the Langflow repository to add your bundle's icon.
The path for your new component icon is `src > frontend > src > icons > DarthVader`
You can view the [icons folder](https://github.com/langflow-ai/langflow/tree/main/src/frontend/src/icons) in the Langflow repository.
To add your icon, create **three** files inside the `icons/darth_vader` folder.

2. In the `icons/darth_vader` folder, add the raw SVG file of your icon, such as `darth_vader-icon.svg`.
:::tip
To convert the SVG file to JSX format, you can use an online tool like SVG to JSX.
It's highly recommended to use the original, lighter version of the SVG.
:::
3. In the `icons/darth_vader` folder, add the icon as a React component in JSX format, such as `DarthVaderIcon.jsx`.
4. Update the JSX file to include the correct component name and structure.
Ensure you include the `{...props}` spread operator in your JSX file.
For example, here is `DarthVaderIcon.jsx`:
```javascript
const DarthVaderIcon = (props) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    width={24}
    height={24}
    viewBox="0 0 32 32"
    fill="none"
    style={{ backgroundColor: "#9100ff", borderRadius: "6px" }}
    {...props}
  >
    <g transform="translate(7, 7)">
      <path
        fillRule="evenodd"
        clipRule="evenodd"
        d="M6.27406 0.685082C8.46664 -0.228361 10.9302 -0.228361 13.1229 0.685082C14.6773 1.33267 16.0054 2.40178 16.9702 3.75502C17.6126 4.65574 17.0835 5.84489 16.045 6.21613L13.5108 7.12189C12.9962 7.30585 12.4289 7.26812 11.9429 7.01756C11.8253 6.95701 11.7298 6.86089 11.6696 6.74266L10.2591 3.97469C10.0249 3.51519 9.37195 3.51519 9.13783 3.97469L7.72731 6.74274C7.66714 6.86089 7.57155 6.95701 7.454 7.01756L4.70187 8.43618C4.24501 8.67169 4.24501 9.3284 4.70187 9.56391L7.454 10.9825C7.57155 11.0431 7.66714 11.1392 7.72731 11.2574L9.13783 14.0254C9.37195 14.4849 10.0249 14.4849 10.2591 14.0254L11.6696 11.2574C11.7298 11.1392 11.8253 11.0431 11.9428 10.9825C12.429 10.7319 12.9965 10.6942 13.5112 10.8781L16.045 11.7838C17.0835 12.1551 17.6126 13.3442 16.9704 14.245C16.0054 15.5982"
        fill={props.isdark === "true" ? "white" : "black"}
      />
    </g>
  </svg>
);

export default DarthVaderIcon;
```

5. In the `icons/darth_vader` folder, add the React component itself in TypeScript format, such as `index.tsx`.
Ensure the icon’s React component name corresponds to the JSX component you just created, such as `DarthVaderIcon`.
```typescript
import { useDarkStore } from "@/stores/darkStore";
import React, { forwardRef } from "react";
import DarthVaderIconSVG from "./DarthVaderIcon";

export const DarthVaderIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  const isdark = useDarkStore((state) => state.dark).toString();

  return <DarthVaderIconSVG ref={ref} isdark={isdark} {...props} />;
});

export default DarthVaderIcon;
```

6. To link your new bundle to the frontend, open `/src/frontend/src/icons/lazyIconImports.ts`.
You can view the [lazyIconImports.ts](https://github.com/langflow-ai/langflow/blob/main/src/frontend/src/icons/lazyIconImports.ts) in the Langflow repository.
7. Add the name of your icon, which should match the icon name you used in the `.tsx` file.
For example:
```typescript
  CrewAI: () =>
    import("@/icons/CrewAI").then((mod) => ({ default: mod.CrewAiIcon })),
  DarthVader: () =>
    import("@/icons/DarthVader").then((mod) => ({ default: mod.DarthVaderIcon })),
  DeepSeek: () =>
    import("@/icons/DeepSeek").then((mod) => ({ default: mod.DeepSeekIcon })),
```

8. To update the bundles sidebar, add the new icon to the `SIDEBAR_BUNDLES` array in `src > frontend > src > utils > styleUtils.ts`.
You can view the [SIDEBAR_BUNDLES array](https://github.com/langflow-ai/langflow/blob/main/src/frontend/src/utils/styleUtils.ts#L231) in the Langflow repository.\
The `name` must point to the folder you created within the `src > backend > base > langflow > components` directory.
For example:
```typescript
{ display_name: "AssemblyAI", name: "assemblyai", icon: "AssemblyAI" },
{ display_name: "DarthVader", name: "darth_vader", icon: "DarthVader" },
{ display_name: "DataStax", name: "astra_assistants", icon: "DarthVader" },
```

## Update bundle components with icons

In your component bundle, associate the icon variable with your new bundle.

In your `darth_vader_component.py` file, in the component class, include the icon that you defined in the frontend.
The `icon` must point to the directory you created for your icons within the `src > frontend > src > icons` directory.
For example:
```
class DarthVaderAPIComponent(LCToolComponent):
    display_name: str = "Darth Vader Tools"
    description: str = "Use the force to run actions with your agent"
    name = "DarthVaderAPI"
    icon = "DarthVader"
```

## Ensure the application builds your component bundle

1. To rebuild the backend and frontend, run `make install_frontend && make build_frontend && make install_backend && uv run langflow run --port 7860`.

2. Refresh the frontend application.
Your new bundle called `DarthVader` is available in the sidebar.