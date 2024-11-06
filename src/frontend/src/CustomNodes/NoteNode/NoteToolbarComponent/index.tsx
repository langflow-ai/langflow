import ShadTooltip from "@/components/shadTooltipComponent";
import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
} from "@/components/ui/select-custom";
import { COLOR_OPTIONS } from "@/constants/constants";
import ToolbarSelectItem from "@/pages/FlowPage/components/nodeToolbarComponent/toolbarSelectItem";
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useShortcutsStore } from "@/stores/shortcuts";
import { noteDataType } from "@/types/flow";
import { classNames, cn, openInNewTab } from "@/utils/utils";
import { cloneDeep } from "lodash";
import IconComponent from "../../../components/genericIconComponent";

export default function NoteToolbarComponent({
  data,
  bgColor,
}: {
  data: noteDataType;
  bgColor: string;
}) {
  const setNoticeData = useAlertStore((state) => state.setNoticeData);
  const nodes = useFlowStore((state) => state.nodes);
  const setLastCopiedSelection = useFlowStore(
    (state) => state.setLastCopiedSelection,
  );
  const paste = useFlowStore((state) => state.paste);
  const shortcuts = useShortcutsStore((state) => state.shortcuts);
  const takeSnapshot = useFlowsManagerStore((state) => state.takeSnapshot);
  const deleteNode = useFlowStore((state) => state.deleteNode);
  const setNode = useFlowStore((state) => state.setNode);

  function openDocs() {
    if (data.node?.documentation) {
      return openInNewTab(data.node?.documentation);
    }
    setNoticeData({
      title: `${data.id} docs is not available at the moment.`,
    });
  }

  const handleSelectChange = (event) => {
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
  };
  // the deafult value is allways the first one if none is provided
  return (
    <>
      <div className="w-26 noflow nowheel nopan nodelete nodrag h-10">
        <span className="isolate inline-flex rounded-md shadow-sm">
          <Popover>
            <ShadTooltip content="Color pick">
              <PopoverTrigger>
                <div>
                  <div
                    data-testid="color_picker"
                    className="relative inline-flex items-center rounded-l-md bg-background px-2 py-2 text-foreground shadow-md transition-all duration-500 ease-in-out hover:bg-muted focus:z-10"
                  >
                    <div
                      style={{
                        backgroundColor: COLOR_OPTIONS[bgColor] ?? "#00000000",
                      }}
                      className={cn(
                        "h-4 w-4 rounded-full",
                        COLOR_OPTIONS[bgColor] === null && "border",
                      )}
                    ></div>
                  </div>
                </div>
              </PopoverTrigger>
            </ShadTooltip>
            <PopoverContent side="top" className="w-fit px-2 py-2">
              <div className="flew-row flex gap-3">
                {Object.entries(COLOR_OPTIONS).map(([color, code]) => {
                  return (
                    <Button
                      data-testid={`color_picker_button_${color}`}
                      unstyled
                      key={color}
                      onClick={() => {
                        setNode(data.id, (old) => ({
                          ...old,
                          data: {
                            ...old.data,
                            node: {
                              ...old.data.node,
                              template: {
                                ...old.data.node?.template,
                                backgroundColor: color,
                              },
                            },
                          },
                        }));
                      }}
                    >
                      <div
                        className={cn(
                          "h-4 w-4 rounded-full hover:border hover:border-ring",
                          bgColor === color ? "border-2 border-blue-500" : "",
                          code === null && "border",
                        )}
                        style={{
                          backgroundColor: code ?? "#00000000",
                        }}
                      ></div>
                    </Button>
                  );
                })}
              </div>
            </PopoverContent>
          </Popover>
          <Select onValueChange={handleSelectChange} value="">
            <ShadTooltip content="All" side="top">
              <SelectTrigger>
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
              </SelectTrigger>
            </ShadTooltip>
            <SelectContent>
              <SelectItem value={"duplicate"}>
                <ToolbarSelectItem
                  shortcut={
                    shortcuts.find((obj) => obj.name === "Duplicate")?.shortcut!
                  }
                  value={"Duplicate"}
                  icon={"Copy"}
                  dataTestId="copy-button-modal"
                />
              </SelectItem>
              <SelectItem value={"copy"}>
                <ToolbarSelectItem
                  shortcut={
                    shortcuts.find((obj) => obj.name === "Copy")?.shortcut!
                  }
                  value={"Copy"}
                  icon={"Clipboard"}
                  dataTestId="copy-button-modal"
                />
              </SelectItem>
              <SelectItem
                value={"documentation"}
                disabled={data.node?.documentation === ""}
              >
                <ToolbarSelectItem
                  shortcut={
                    shortcuts.find((obj) => obj.name === "Docs")?.shortcut!
                  }
                  value={"Docs"}
                  icon={"FileText"}
                  dataTestId="docs-button-modal"
                />
              </SelectItem>
              <SelectItem value={"delete"} className="focus:bg-red-400/[.20]">
                <div className="font-red flex text-status-red">
                  <IconComponent
                    name="Trash2"
                    className="relative top-0.5 mr-2 h-4 w-4"
                  />{" "}
                  <span className="">Delete</span>{" "}
                  <span className="absolute right-2 top-2 flex items-center justify-center rounded-sm px-1 py-[0.2]">
                    <IconComponent
                      name="Delete"
                      className="h-4 w-4 stroke-2 text-red-400"
                    ></IconComponent>
                  </span>
                </div>
              </SelectItem>
            </SelectContent>
          </Select>
        </span>
      </div>
    </>
  );
}
