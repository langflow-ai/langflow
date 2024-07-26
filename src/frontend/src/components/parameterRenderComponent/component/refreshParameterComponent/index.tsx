import { RefreshButton } from "@/components/ui/refreshButton";
import { usePostTemplateValue } from "@/controllers/API/queries/nodes/use-post-template-value";
import { mutateTemplate } from "@/CustomNodes/helpers/mutate-template";
import useAlertStore from "@/stores/alertStore";

export function RefreshParameterComponent({
  children,
  templateData,
  disabled,
  nodeClass,
  handleNodeClass,
  nodeId,
  name,
}) {
  const postTemplateValue = usePostTemplateValue({
    parameterId: name,
    nodeId: nodeId,
    node: nodeClass,
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
  return (
    <div className="flex w-full items-center gap-2">
      <div className="w-full">{children}</div>
      {templateData.refresh_button && (
        <div className="w-1/6">
          <RefreshButton
            isLoading={postTemplateValue.isPending}
            disabled={disabled}
            button_text={templateData.refresh_button_text}
            handleUpdateValues={handleRefreshButtonPress}
            id={"refresh-button-" + name}
          />
        </div>
      )}
    </div>
  );
}
