import { debounce } from "lodash";
import { SAVE_DEBOUNCE_TIME } from "../constants/constants";
import { postCustomComponentUpdate } from "../controllers/API";
import { NodeDataType } from "../types/flow";

export const handleUpdateValues = async (name: string, data: NodeDataType) => {
  const code = data.node?.template?.code?.value;
  if (!code) {
    console.error("Code not found in the template");
    return;
  }

  const template = data.node?.template;
  if (!template) {
    console.error("No template found in the node.");
    return;
  }

  try {
    const res = await postCustomComponentUpdate(
      code,
      template,
      name,
      data.node?.template[name]?.value,
    );
    if (res.status === 200 && data.node?.template) {
      return res.data.template;
    }
  } catch (error) {
    console.error("Error occurred while updating the node:", error);
    throw error;
  }
};

export const debouncedHandleUpdateValues = debounce(
  handleUpdateValues,
  SAVE_DEBOUNCE_TIME,
);
