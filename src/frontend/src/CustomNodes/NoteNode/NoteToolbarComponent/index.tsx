import ShadTooltip from "@/components/common/shadTooltipComponent";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Select, SelectTrigger } from "@/components/ui/select-custom";
import { COLOR_OPTIONS } from "@/constants/constants";
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useShortcutsStore } from "@/stores/shortcuts";
import { NoteDataType } from "@/types/flow";
import { classNames, cn, openInNewTab } from "@/utils/utils";
import { cloneDeep } from "lodash";
import { memo, useCallback, useMemo } from "react";
import IconComponent from "../../../components/common/genericIconComponent";
import { ColorPickerButtons } from "../components/color-picker-buttons";
import { SelectItems } from "../components/select-items";

const NoteToolbarComponent = memo(function NoteToolbarComponent({
  data,
  bgColor,
}: {
  data: NoteDataType;
  bgColor: string;
}) {
  const setNoticeData = useAlertStore((state) => state.setNoticeData);

  // Combine multiple store selectors into one to reduce re-renders
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

  const takeSnapshot = useFlowsManagerStore((state) => state.takeSnapshot);
  const shortcuts = useShortcutsStore((state) => state.shortcuts);

  const openDocs = useCallback(() => {
    if (data.node?.documentation) {
      return openInNewTab(data.node?.documentation);
    }
    setNoticeData({
      title: `${data.id} docs is not available at the moment.`,
    });
  }, [data.node?.documentation, data.id, setNoticeData]);

  const handleSelectChange = useCallback(
    (event: string) => {
      switch (event) {
        case "documentation":
          openDocs();
          break;
        case "delete":
          takeSnapshot();
          deleteNode(data.id);
          break;
        case "copy":
          const node = nodes.filter((node) => node.id === data.id);
          setLastCopiedSelection({ nodes: cloneDeep(node), edges: [] });
          break;
        case "duplicate":
          paste(
            {
              nodes: [nodes.find((node) => node.id === data.id)!],
              edges: [],
            },
            {
              x: 50,
              y: 10,
              paneX: nodes.find((node) => node.id === data.id)?.position.x,
              paneY: nodes.find((node) => node.id === data.id)?.position.y,
            },
          );
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

  // Memoize the color picker background style
  const colorPickerStyle = useMemo(
    () => ({
      backgroundColor: COLOR_OPTIONS[bgColor] ?? "#00000000",
    }),
    [bgColor],
  );

  return (
    <div className="w-26 noflow nowheel nopan nodelete nodrag h-10">
      <span className="isolate inline-flex rounded-md shadow-sm">
        <Popover>
          <ShadTooltip content="Pick Color">
            <PopoverTrigger>
              <div>
                <div
                  data-testid="color_picker"
                  className="relative inline-flex items-center rounded-l-md bg-background px-2 py-2 text-foreground shadow-md transition-all duration-500 ease-in-out hover:bg-muted focus:z-10"
                >
                  <div
                    style={colorPickerStyle}
                    className={cn(
                      "h-4 w-4 rounded-full",
                      COLOR_OPTIONS[bgColor] === null && "border",
                    )}
                  />
                </div>
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

        <Select onValueChange={handleSelectChange} value="">
          <SelectTrigger>
            <ShadTooltip content="Show More" side="top">
              <div>
                <div
                  data-testid="more-options-modal"
                  className={classNames(
                    "relative -ml-px inline-flex h-8 w-[2rem] items-center rounded-r-md bg-background text-foreground shadow-md transition-all duration-500 ease-in-out hover:bg-muted focus:z-10",
                  )}
                >
                  <IconComponent
                    name="MoreHorizontal"
                    className="relative left-2 h-4 w-4"
                  />
                </div>
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
