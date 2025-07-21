import type { FlowType } from "@/types/flow";
import { cn } from "../../../../../utils/utils";
import ForwardedIconComponent from "../../../../common/genericIconComponent";
import { Card, CardHeader, CardTitle } from "../../../../ui/card";

export default function DragCardComponent({ data }: { data: FlowType }) {
  return (
    <>
      <Card
        draggable
        //TODO check color schema
        className={cn(
          "group relative flex flex-col justify-between overflow-hidden transition-all hover:bg-muted/50 hover:shadow-md hover:dark:bg-[#ffffff10]",
        )}
      >
        <div>
          <CardHeader>
            <div>
              <CardTitle className="flex w-full items-start justify-between gap-3 text-xl">
                <ForwardedIconComponent
                  className={cn(
                    "visible flex-shrink-0",
                    data.is_component
                      ? "mx-0.5 h-6 w-6 text-component-icon"
                      : "h-7 w-7 flex-shrink-0 text-flow-icon",
                  )}
                  name={data.is_component ? "ToyBrick" : "Group"}
                />

                <div className="w-full truncate pr-3">{data.name}</div>
              </CardTitle>
            </div>
          </CardHeader>
        </div>
      </Card>
    </>
  );
}
