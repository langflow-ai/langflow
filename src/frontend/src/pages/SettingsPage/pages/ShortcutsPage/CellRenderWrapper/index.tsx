import RenderIcons from "@/components/common/renderIconComponent";
import { CustomCellRendererProps } from "ag-grid-react";

export default function CellRenderShortcuts(params: CustomCellRendererProps) {
  const shortcut = params.value;
  const splitShortcut = shortcut?.split("+");
  return <RenderIcons filteredShortcut={splitShortcut} tableRender />;
}
