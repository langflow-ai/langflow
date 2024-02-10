import { useEffect, useRef, useState } from "react";
import ShadTooltip from "../../../../../components/ShadTooltipComponent";
import IconComponent from "../../../../../components/genericIconComponent";
import { Badge } from "../../../../../components/ui/badge";
import { nodeColors } from "../../../../../utils/styleUtils";
import { cn } from "../../../../../utils/utils";

export default function SideBarAccordeon({
  title,
  icon,
  tagVisible,
}: {
  title: string;
  icon: string;
  tagVisible: boolean;
}) {
  const doisRef = useRef<HTMLDivElement>(null);
  const [doisSizeRef, setDoisSizeRef] = useState(
    doisRef?.current?.clientHeight ?? 0
  );
  const [seeMore2, setSeeMore2] = useState(false);
  useEffect(() => {
    setDoisSizeRef(doisRef?.current?.clientHeight ?? 0);
  }, [doisRef]);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <span className="flex items-center gap-3 px-2 text-xl font-semibold tracking-tight">
          <IconComponent name={icon} className="h-6 w-6" />
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
          seeMore2 ? "h-[" + doisSizeRef + "px]" : (tagVisible ? "h-40": "h-32")
        )}
      >
        <div className="grid h-fit grid-cols-2 gap-4" ref={doisRef}>
          <div
            className={cn("flex cursor-grab flex-col overflow-hidden rounded-lg border bg-background transition-all hover:shadow-lg ", tagVisible ? "h-40": "h-32")}
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
            {tagVisible && (
              <div className="flex w-full flex-1 flex-shrink-0 flex-wrap gap-2 px-4 pb-4">
                <Badge variant="gray" size="xq">
                  Vector Store
                </Badge>
                <Badge variant="gray" size="xq">
                  OpenAI
                </Badge>
                <Badge variant="gray" size="xq">
                  Chain
                </Badge>
              </div>
            )}
          </div>
          <div
            className={cn("flex cursor-grab flex-col overflow-hidden rounded-lg border bg-background transition-all hover:shadow-lg ", tagVisible ? "h-40": "h-32")}
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
            {tagVisible && (
              <div className="flex w-full flex-1 flex-shrink-0 flex-wrap gap-2 px-4 pb-4">
                <Badge variant="gray" size="xq">
                  Vector Store
                </Badge>
                <Badge variant="gray" size="xq">
                  OpenAI
                </Badge>
                <Badge variant="gray" size="xq">
                  Chain
                </Badge>
              </div>
            )}
          </div>
          <div
            className={cn("flex cursor-grab flex-col overflow-hidden rounded-lg border bg-background transition-all hover:shadow-lg ", tagVisible ? "h-40": "h-32")}
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
            {tagVisible && (
              <div className="flex w-full flex-1 flex-shrink-0 flex-wrap gap-2 px-4 pb-4">
                <Badge variant="gray" size="xq">
                  Vector Store
                </Badge>
                <Badge variant="gray" size="xq">
                  OpenAI
                </Badge>
                <Badge variant="gray" size="xq">
                  Chain
                </Badge>
              </div>
            )}
          </div>
          <div
            className={cn("flex cursor-grab flex-col overflow-hidden rounded-lg border bg-background transition-all hover:shadow-lg ", tagVisible ? "h-40": "h-32")}
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
            {tagVisible && (
              <div className="flex w-full flex-1 flex-shrink-0 flex-wrap gap-2 px-4 pb-4">
                <Badge variant="gray" size="xq">
                  Vector Store
                </Badge>
                <Badge variant="gray" size="xq">
                  OpenAI
                </Badge>
                <Badge variant="gray" size="xq">
                  Chain
                </Badge>
              </div>
            )}
          </div>
          <div
            className={cn("flex cursor-grab flex-col overflow-hidden rounded-lg border bg-background transition-all hover:shadow-lg ", tagVisible ? "h-40": "h-32")}
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
            {tagVisible && (
              <div className="flex w-full flex-1 flex-shrink-0 flex-wrap gap-2 px-4 pb-4">
                <Badge variant="gray" size="xq">
                  Vector Store
                </Badge>
                <Badge variant="gray" size="xq">
                  OpenAI
                </Badge>
                <Badge variant="gray" size="xq">
                  Chain
                </Badge>
              </div>
            )}
          </div>
          <div
            className={cn("flex cursor-grab flex-col overflow-hidden rounded-lg border bg-background transition-all hover:shadow-lg ", tagVisible ? "h-40": "h-32")}
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
            {tagVisible && (
              <div className="flex w-full flex-1 flex-shrink-0 flex-wrap gap-2 px-4 pb-4">
                <Badge variant="gray" size="xq">
                  Vector Store
                </Badge>
                <Badge variant="gray" size="xq">
                  OpenAI
                </Badge>
                <Badge variant="gray" size="xq">
                  Chain
                </Badge>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
