import type { Dispatch, SetStateAction } from "react";
import { mutateTemplate } from "@/CustomNodes/helpers/mutate-template";
import { usePostTemplateValue } from "@/controllers/API/queries/nodes/use-post-template-value";
import useAlertStore from "@/stores/alertStore";
import type { APIClassType } from "@/types/api";

/**
 * Template-mutation flows for the dropdown: creating from a source
 * option and refreshing the options list, moved verbatim from the
 * component. Owns the post-template-value mutation and error alert.
 */
export function useDropdownMutations({
  value,
  name,
  nodeId,
  nodeClass,
  handleNodeClass,
  setOpen,
  setWaitingForResponse,
  setRefreshOptions,
}: {
  value: string;
  name?: string;
  nodeId?: string;
  nodeClass?: APIClassType;
  // biome-ignore lint/suspicious/noExplicitAny: legacy
  handleNodeClass?: (value: any, code?: string, type?: string) => void;
  setOpen: Dispatch<SetStateAction<boolean>>;
  setWaitingForResponse: Dispatch<SetStateAction<boolean>>;
  setRefreshOptions: Dispatch<SetStateAction<boolean>>;
}) {
  // API and store hooks
  const postTemplateValue = usePostTemplateValue({
    parameterId: name,
    nodeId: nodeId,
    node: nodeClass,
  });
  const setErrorData = useAlertStore((state) => state.setErrorData);

  const handleSourceOptions = async (value: string) => {
    setWaitingForResponse(true);
    setOpen(false);

    await mutateTemplate(
      value,
      nodeId,
      nodeClass!,
      handleNodeClass,
      postTemplateValue,
      setErrorData,
      name,
    );

    setWaitingForResponse(false);
  };

  const handleRefreshButtonPress = async () => {
    setRefreshOptions(true);
    setOpen(false);

    await mutateTemplate(
      value,
      nodeId,
      nodeClass!,
      handleNodeClass,
      postTemplateValue,
      setErrorData,
      undefined, // parameterName
      undefined, // callback
      undefined, // toolMode
      true, // isRefresh
    )?.then(() => {
      setTimeout(() => {
        setRefreshOptions(false);
      }, 2000);
    });
  };

  return { handleSourceOptions, handleRefreshButtonPress };
}
