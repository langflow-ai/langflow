import { ENABLE_NEW_IO_MODAL } from "@/customization/feature-flags";
import { track } from "@/customization/utils/analytics";
import { useState } from "react";
import { Control } from "react-hook-form";
import IOModalOld from "../../modals/IOModal";
import IOModalNew from "../../modals/IOModal/newModal";
import useAlertStore from "../../stores/alertStore";
import useFlowsManagerStore from "../../stores/flowsManagerStore";
import { FlowType } from "../../types/flow";
import { getInputsAndOutputs } from "../../utils/storeUtils";
import { cn } from "../../utils/utils";
import IconComponent from "../genericIconComponent";
import ShadTooltip from "../shadTooltipComponent";
import { Button } from "../ui/button";
import {
  Card,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "../ui/card";
import { Checkbox } from "../ui/checkbox";
import { FormControl, FormField } from "../ui/form";
import Loading from "../ui/loading";
import useDragStart from "./hooks/use-on-drag-start";
import { convertTestName } from "./utils/convert-test-name";
const IOModal = ENABLE_NEW_IO_MODAL ? IOModalNew : IOModalOld;

export default function CollectionCardComponent({
  data,
  disabled = false,
  onClick,
  control,
}: {
  data: FlowType;
  disabled?: boolean;
  onClick?: () => void;
  control?: Control<any, any>;
}) {
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const setCurrentFlow = useFlowsManagerStore((state) => state.setCurrentFlow);
  const getFlowById = useFlowsManagerStore((state) => state.getFlowById);
  // const [openPlayground, setOpenPlayground] = useState(false);
  const [loadingPlayground, setLoadingPlayground] = useState(false);
  const selectedFlowsComponentsCards = useFlowsManagerStore(
    (state) => state.selectedFlowsComponentsCards,
  );

  function hasPlayground(flow?: FlowType) {
    if (!flow) {
      return false;
    }
    const { inputs, outputs } = getInputsAndOutputs(flow?.data?.nodes ?? []);
    return inputs.length > 0 || outputs.length > 0;
  }
  const playground = !(data.is_component ?? false);
  const isSelectedCard =
    selectedFlowsComponentsCards?.includes(data?.id) ?? false;

  const { onDragStart } = useDragStart(data);

  const handlePlaygroundClick = (e: React.MouseEvent<HTMLButtonElement>) => {
    e.preventDefault();
    e.stopPropagation();
    track("Playground Button Clicked", { flowId: data.id });
    setLoadingPlayground(true);

    if (data) {
      if (!hasPlayground(data)) {
        setErrorData({
          title: "Error",
          list: ["This flow doesn't have a playground."],
        });
        setLoadingPlayground(false);
        return;
      }
      setCurrentFlow(data);
      // setOpenPlayground(true);
      setLoadingPlayground(false);
    } else {
      setErrorData({
        title: "Error",
        list: ["Error getting flow data."],
      });
    }
  };

  return (
    <>
      <Card
        onDragStart={onDragStart}
        draggable
        data-testid={`card-${convertTestName(data.name)}`}
        //TODO check color schema
        className={cn(
          "group relative flex h-[11rem] flex-col justify-between overflow-hidden",
          !data.is_component &&
            "hover:bg-muted/50 hover:shadow-md hover:dark:bg-[#5f5f5f0e]",
          disabled ? "pointer-events-none opacity-50" : "",
          onClick ? "cursor-pointer" : "",
          isSelectedCard ? "border border-selected" : "",
        )}
        onClick={onClick}
      >
        <div>
          <CardHeader>
            <div>
              <CardTitle className="flex w-full items-start justify-between gap-3 text-xl">
                <IconComponent
                  className={cn(
                    "visible flex-shrink-0",
                    data.is_component
                      ? "mx-0.5 h-6 w-6 text-component-icon"
                      : "h-7 w-7 flex-shrink-0 text-flow-icon",
                  )}
                  name={data.is_component ? "ToyBrick" : "Group"}
                />
                <ShadTooltip content={data.name}>
                  <div className="w-full truncate pr-3">{data.name}</div>
                </ShadTooltip>
                {control && (
                  <div
                    className="flex"
                    onClick={(e) => {
                      e.stopPropagation();
                    }}
                  >
                    <FormField
                      control={control}
                      name={`${data.id}`}
                      defaultValue={false}
                      render={({ field }) => (
                        <FormControl>
                          <Checkbox
                            data-testid={`checkbox-component`}
                            aria-label="checkbox-component"
                            checked={field.value}
                            onCheckedChange={field.onChange}
                            className="h-5 w-5 border border-ring data-[state=checked]:border-selected data-[state=checked]:bg-selected"
                          />
                        </FormControl>
                      )}
                    />
                  </div>
                )}
              </CardTitle>
            </div>
            <div className="flex gap-2">
              <div className="flex w-full flex-1 flex-wrap gap-2"></div>
            </div>
            <CardDescription className="pb-2 pt-2">
              <div className="truncate-doubleline">{data.description}</div>
            </CardDescription>
          </CardHeader>
        </div>
        <CardFooter>
          <div className="z-50 flex w-full items-center justify-between gap-2">
            <div className="flex w-full flex-wrap items-end justify-end gap-2">
              {/* {playground && (
                <Button
                  disabled={loadingPlayground || !hasPlayground(data)}
                  key={data.id}
                  tabIndex={-1}
                  variant="primary"
                  size="sm"
                  className="gap-2 whitespace-nowrap bg-muted"
                  data-testid={"playground-flow-button-" + data.id}
                  onClick={handlePlaygroundClick}
                >
                  {!loadingPlayground ? (
                    <IconComponent
                      name="BotMessageSquareIcon"
                      className="h-4 w-4 select-none"
                    />
                  ) : (
                    <Loading className="h-4 w-4 text-medium-indigo" />
                  )}
                  Playground
                </Button>
              )} */}
            </div>
          </div>
        </CardFooter>
      </Card>
      {/* {openPlayground && (
        <IOModal
          key={data.id}
          cleanOnClose={true}
          open={openPlayground}
          setOpen={setOpenPlayground}
        >
          <></>
        </IOModal>
      )} */}
    </>
  );
}
