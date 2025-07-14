import { FlowType } from "@/types/flow";
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
          "group hover:bg-muted/50 relative flex flex-col justify-between overflow-hidden transition-all hover:shadow-md dark:hover:bg-[#ffffff10]",
        )}
      >
        <div>
          <CardHeader>
            <div>
              <CardTitle className="flex w-full items-start justify-between gap-3 text-xl">
                <ForwardedIconComponent
                  className={cn(
                    "visible shrink-0",
                    data.is_component
                      ? "text-component-icon mx-0.5 h-6 w-6"
                      : "text-flow-icon h-7 w-7 shrink-0",
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
