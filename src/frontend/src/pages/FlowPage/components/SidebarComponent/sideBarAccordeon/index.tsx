import { cloneDeep } from "lodash";
import { useEffect, useMemo, useRef, useState } from "react";
import ShadTooltip from "../../../../../components/ShadTooltipComponent";
import IconComponent from "../../../../../components/genericIconComponent";
import { TagsSelector } from "../../../../../components/tagsSelectorComponent";
import { Badge } from "../../../../../components/ui/badge";
import { Button } from "../../../../../components/ui/button";
import { Input } from "../../../../../components/ui/input";
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from "../../../../../components/ui/resizable";
import ExportModal from "../../../../../modals/exportModal";
import ShareModal from "../../../../../modals/shareModal";
import useAlertStore from "../../../../../stores/alertStore";
import useFlowStore from "../../../../../stores/flowStore";
import useFlowsManagerStore from "../../../../../stores/flowsManagerStore";
import { useStoreStore } from "../../../../../stores/storeStore";
import { useTypesStore } from "../../../../../stores/typesStore";
import { APIClassType, APIObjectType } from "../../../../../types/api";
import { nodeColors } from "../../../../../utils/styleUtils";
import { classNames, cn } from "../../../../../utils/utils";

export default function SideBarAccordeon({title}: {title: string}) {
    const doisRef = useRef<HTMLDivElement>(null);
    const [doisSizeRef, setDoisSizeRef] = useState(doisRef?.current?.clientHeight ?? 0);
    const [seeMore2, setSeeMore2] = useState(false);
    useEffect(() => {setDoisSizeRef(doisRef?.current?.clientHeight ?? 0)}, [doisRef])

    return (
        <div className="space-y-4">

            <div className="flex items-center justify-between">
              <span className="px-2 text-xl font-semibold tracking-tight">
                {title}
              </span>
              <button
                onClick={() => {
                  setSeeMore2((old) => !old);
                }}
                className="flex items-center gap-2 text-sm"
              >
                See {seeMore2 ? "Less" : "More"}
                <IconComponent
                  name="ChevronDown"
                  className={cn(
                    "h-5 w-5 text-muted-foreground transition-all duration-300",
                    seeMore2 ? "rotate-180 transform" : ""
                  )}
                />
              </button>
            </div>
            <div
              className={cn(
                "overflow-hidden transition-all duration-500 ease-in-out",
                seeMore2 ? "h-[" + doisSizeRef + "px]" : "h-32"
              )}
            >
              <div className="grid h-fit grid-cols-2 gap-4" ref={doisRef}>
                <div
                  className="flex h-32 cursor-grab flex-col overflow-hidden rounded-lg border bg-background transition-all hover:shadow-lg "
                  draggable={true}
                >
                  <div
                    className={
                      "flex-max-width flex-shrink-0 items-center truncate p-2"
                    }
                  >
                    <IconComponent
                      name={"group_components"}
                      className={"generic-node-icon "}
                      iconColor={`${nodeColors["chains"]}`}
                    />
                    <div className="truncate">
                      <ShadTooltip content={"My Component"}>
                        <div className="flex" onDoubleClick={() => {}}>
                          <div
                            data-testid={"title-" + "My Component"}
                            className="ml-2 truncate pr-2 text-primary"
                          >
                            My Component
                          </div>
                        </div>
                      </ShadTooltip>
                    </div>
                    <IconComponent
                      name="Info"
                      className="ml-1 h-4 w-4 text-muted-foreground"
                    />
                  </div>
                  <div className="h-full px-4 text-sm text-muted-foreground truncate-doubleline">
                    The description will tell the user what to do or why use it.
                  </div>
                  
                </div>
                <div
                  className="flex h-32 cursor-grab flex-col overflow-hidden rounded-lg border bg-background transition-all hover:shadow-lg "
                  draggable={true}
                >
                  <div
                    className={
                      "flex-max-width flex-shrink-0 items-center truncate p-2"
                    }
                  >
                    <IconComponent
                      name={"group_components"}
                      className={"generic-node-icon "}
                      iconColor={`${nodeColors["chains"]}`}
                    />
                    <div className="truncate">
                      <ShadTooltip content={"My Component"}>
                        <div className="flex" onDoubleClick={() => {}}>
                          <div
                            data-testid={"title-" + "My Component"}
                            className="ml-2 truncate pr-2 text-primary"
                          >
                            My Component
                          </div>
                        </div>
                      </ShadTooltip>
                    </div>
                    <IconComponent
                      name="Info"
                      className="ml-1 h-4 w-4 text-muted-foreground"
                    />
                  </div>
                  <div className="h-full px-4 text-sm text-muted-foreground truncate-doubleline">
                    The description will tell the user what to do or why use it.
                  </div>
                  
                </div>
                <div
                  className="flex h-32 cursor-grab flex-col overflow-hidden rounded-lg border bg-background transition-all hover:shadow-lg "
                  draggable={true}
                >
                  <div
                    className={
                      "flex-max-width flex-shrink-0 items-center truncate p-2"
                    }
                  >
                    <IconComponent
                      name={"group_components"}
                      className={"generic-node-icon "}
                      iconColor={`${nodeColors["chains"]}`}
                    />
                    <div className="truncate">
                      <ShadTooltip content={"My Component"}>
                        <div className="flex" onDoubleClick={() => {}}>
                          <div
                            data-testid={"title-" + "My Component"}
                            className="ml-2 truncate pr-2 text-primary"
                          >
                            My Component
                          </div>
                        </div>
                      </ShadTooltip>
                    </div>
                    <IconComponent
                      name="Info"
                      className="ml-1 h-4 w-4 text-muted-foreground"
                    />
                  </div>
                  <div className="h-full px-4 text-sm text-muted-foreground truncate-doubleline">
                    The description will tell the user what to do or why use it.
                  </div>
                  
                </div>
                <div
                  className="flex h-32 cursor-grab flex-col overflow-hidden rounded-lg border bg-background transition-all hover:shadow-lg "
                  draggable={true}
                >
                  <div
                    className={
                      "flex-max-width flex-shrink-0 items-center truncate p-2"
                    }
                  >
                    <IconComponent
                      name={"group_components"}
                      className={"generic-node-icon "}
                      iconColor={`${nodeColors["chains"]}`}
                    />
                    <div className="truncate">
                      <ShadTooltip content={"My Component"}>
                        <div className="flex" onDoubleClick={() => {}}>
                          <div
                            data-testid={"title-" + "My Component"}
                            className="ml-2 truncate pr-2 text-primary"
                          >
                            My Component
                          </div>
                        </div>
                      </ShadTooltip>
                    </div>
                    <IconComponent
                      name="Info"
                      className="ml-1 h-4 w-4 text-muted-foreground"
                    />
                  </div>
                  <div className="h-full px-4 text-sm text-muted-foreground truncate-doubleline">
                    The description will tell the user what to do or why use it.
                  </div>
                  
                </div>
                <div
                  className="flex h-32 cursor-grab flex-col overflow-hidden rounded-lg border bg-background transition-all hover:shadow-lg "
                  draggable={true}
                >
                  <div
                    className={
                      "flex-max-width flex-shrink-0 items-center truncate p-2"
                    }
                  >
                    <IconComponent
                      name={"group_components"}
                      className={"generic-node-icon "}
                      iconColor={`${nodeColors["chains"]}`}
                    />
                    <div className="truncate">
                      <ShadTooltip content={"My Component"}>
                        <div className="flex" onDoubleClick={() => {}}>
                          <div
                            data-testid={"title-" + "My Component"}
                            className="ml-2 truncate pr-2 text-primary"
                          >
                            My Component
                          </div>
                        </div>
                      </ShadTooltip>
                    </div>
                    <IconComponent
                      name="Info"
                      className="ml-1 h-4 w-4 text-muted-foreground"
                    />
                  </div>
                  <div className="h-full px-4 text-sm text-muted-foreground truncate-doubleline">
                    The description will tell the user what to do or why use it.
                  </div>
                  
                </div>
                <div
                  className="flex h-32 cursor-grab flex-col overflow-hidden rounded-lg border bg-background transition-all hover:shadow-lg "
                  draggable={true}
                >
                  <div
                    className={
                      "flex-max-width flex-shrink-0 items-center truncate p-2"
                    }
                  >
                    <IconComponent
                      name={"group_components"}
                      className={"generic-node-icon "}
                      iconColor={`${nodeColors["chains"]}`}
                    />
                    <div className="truncate">
                      <ShadTooltip content={"My Component"}>
                        <div className="flex" onDoubleClick={() => {}}>
                          <div
                            data-testid={"title-" + "My Component"}
                            className="ml-2 truncate pr-2 text-primary"
                          >
                            My Component
                          </div>
                        </div>
                      </ShadTooltip>
                    </div>
                    <IconComponent
                      name="Info"
                      className="ml-1 h-4 w-4 text-muted-foreground"
                    />
                  </div>
                  <div className="h-full px-4 text-sm text-muted-foreground truncate-doubleline">
                    The description will tell the user what to do or why use it.
                  </div>
                  
                </div>
              </div>
            </div>
            </div>
    )
}