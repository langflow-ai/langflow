import { RefreshButton } from "@/components/ui/refreshButton";
import { FLEX_VIEW_TYPES } from "@/constants/constants";
import { usePostTemplateValue } from "@/controllers/API/queries/nodes/use-post-template-value";
import { mutateTemplate } from "@/CustomNodes/helpers/mutate-template";
import useAlertStore from "@/stores/alertStore";
import { APIClassType, InputFieldType } from "@/types/api";
import { cn } from "@/utils/utils";
import { InputProps } from "../../types";

export function RefreshParameterComponent({
  children,
  templateData,
  disabled,
  nodeClass,
  editNode,
  handleNodeClass,
  nodeId,
  name,
}: {
  children: React.ReactElement<InputProps>;
  templateData: Partial<InputFieldType>;
  disabled: boolean;
  nodeClass: APIClassType;
  editNode: boolean;
  handleNodeClass: (value: any, code?: string, type?: string) => void;
  nodeId: string;
  name: string;
}) {
  const postTemplateValue = usePostTemplateValue({
    parameterId: name,
    nodeId: nodeId,
    node: nodeClass,
    tool_mode: nodeClass.tool_mode ?? false,
  });

  const setErrorData = useAlertStore((state) => state.setErrorData);
  const handleRefreshButtonPress = () =>
    mutateTemplate(
      templateData.value,
      nodeClass,
      handleNodeClass,
      postTemplateValue,
      setErrorData,
    );

  const isFlexView = FLEX_VIEW_TYPES.includes(templateData.type ?? "");

  return (
    (children || templateData.refresh_button) && (
      <div
        className={cn(
          "flex w-full items-center justify-center gap-3",
          isFlexView ? "justify-end" : "justify-center",
        )}
      >
        {children}
        {templateData.refresh_button && (
          <div className="shrink-0 flex-col">
            <RefreshButton
              isLoading={postTemplateValue.isPending}
              disabled={disabled}
              editNode={editNode}
              button_text={templateData.refresh_button_text}
              handleUpdateValues={handleRefreshButtonPress}
              id={"refresh-button-" + name}
            />
          </div>
        )}
      </div>
    )
  );
}
