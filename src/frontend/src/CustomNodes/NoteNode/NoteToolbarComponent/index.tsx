import { cloneDeep } from "lodash";
import { memo, useCallback, useMemo } from "react";
import IconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Select, SelectTrigger } from "@/components/ui/select-custom";
import { COLOR_OPTIONS } from "@/constants/constants";
import { customOpenNewTab } from "@/customization/utils/custom-open-new-tab";
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useShortcutsStore } from "@/stores/shortcuts";
import type { NoteDataType } from "@/types/flow";
import { cn } from "@/utils/utils";
import { ColorPickerButtons } from "../components/color-picker-buttons";
import { SelectItems } from "../components/select-items";

interface NoteToolbarProps {
  data: NoteDataType;
  bgColor: string;
}

const NoteToolbarComponent = memo(function NoteToolbarComponent({
  data,
  bgColor,
}: NoteToolbarProps) {
  const setNoticeData = useAlertStore((state) => state.setNoticeData);
  const takeSnapshot = useFlowsManagerStore((state) => state.takeSnapshot);
  const shortcuts = useShortcutsStore((state) => state.shortcuts);

  // Batch store selectors to reduce re-renders
  const { nodes, setLastCopiedSelection, paste, setNode, deleteNode } =
    useFlowStore(
      useCallback(
        (state) => ({
          nodes: state.nodes,
          setLastCopiedSelection: state.setLastCopiedSelection,
          paste: state.paste,
          setNode: state.setNode,
          deleteNode: state.deleteNode,
        }),
        [],
      ),
    );

  /** Opens documentation URL or shows notice if unavailable */
  const openDocs = useCallback(() => {
    if (data.node?.documentation) {
      return customOpenNewTab(data.node.documentation);
    }
    setNoticeData({ title: `${data.id} docs is not available at the moment.` });
  }, [data.node?.documentation, data.id, setNoticeData]);

  /** Handles toolbar menu actions: copy, duplicate, delete, documentation */
  const handleSelectChange = useCallback(
    (action: string) => {
      const currentNode = nodes.find((node) => node.id === data.id);

      switch (action) {
        case "documentation":
          openDocs();
          break;

        case "delete":
          takeSnapshot();
          deleteNode(data.id);
          break;

        case "copy":
          if (currentNode) {
            setLastCopiedSelection({
              nodes: cloneDeep([currentNode]),
              edges: [],
            });
          }
          break;

        case "duplicate":
          if (currentNode) {
            paste(
              { nodes: [currentNode], edges: [] },
              {
                x: 50,
                y: 10,
                paneX: currentNode.position.x,
                paneY: currentNode.position.y,
              },
            );
          }
          break;
      }
    },
    [
      openDocs,
      takeSnapshot,
      deleteNode,
      data.id,
      nodes,
      setLastCopiedSelection,
      paste,
    ],
  );

  const isCustomColor =
    bgColor && !Object.keys(COLOR_OPTIONS).includes(bgColor);

  // Memoize resolved background color for the color picker indicator
  const resolvedBgColor = useMemo(
    () => (isCustomColor ? bgColor : (COLOR_OPTIONS[bgColor] ?? "#00000000")),
    [bgColor, isCustomColor],
  );

  const hasVisibleBg = isCustomColor || COLOR_OPTIONS[bgColor] === null;

  return (
    <div className="noflow nowheel nopan nodelete nodrag h-10 w-26">
      <span className="isolate inline-flex rounded-md shadow-sm">
        {/* Color picker popover */}
        <Popover>
          <ShadTooltip content="Pick Color">
            <PopoverTrigger>
              <div
                data-testid="color_picker"
                className="relative inline-flex items-center rounded-l-md bg-background px-2 py-2 text-foreground shadow-md transition-all duration-500 ease-in-out hover:bg-muted focus:z-10"
              >
                <div
                  style={{ backgroundColor: resolvedBgColor }}
                  className={cn(
                    "h-4 w-4 rounded-full",
                    hasVisibleBg && "border",
                  )}
                />
              </div>
            </PopoverTrigger>
          </ShadTooltip>
          <PopoverContent side="top" className="w-fit px-2 py-2">
            <ColorPickerButtons
              bgColor={bgColor}
              data={data}
              setNode={setNode}
            />
          </PopoverContent>
        </Popover>

        {/* More options dropdown */}
        <Select onValueChange={handleSelectChange} value="">
          <SelectTrigger>
            <ShadTooltip content="Show More" side="top">
              <div
                data-testid="more-options-modal"
                className="relative -ml-px inline-flex h-8 w-[2rem] items-center rounded-r-md bg-background text-foreground shadow-md transition-all duration-500 ease-in-out hover:bg-muted focus:z-10"
              >
                <IconComponent
                  name="MoreHorizontal"
                  className="relative left-2 h-4 w-4"
                />
              </div>
            </ShadTooltip>
          </SelectTrigger>
          <SelectItems shortcuts={shortcuts} data={data} />
        </Select>
      </span>
    </div>
  );
});

NoteToolbarComponent.displayName = "NoteToolbarComponent";

export default NoteToolbarComponent;
