import { throttle } from "lodash";
import { postCustomComponentUpdate } from "../controllers/API";
import { ResponseErrorTypeAPI } from "../types/api";
import { NodeDataType } from "../types/flow";

export const handleUpdateValues = async (name: string, data: NodeDataType) => {
  const code = data.node?.template["code"]?.value;
  if (!code) {
    console.error("Code not found in the template");
    return;
  }
  try {
    let newTemplate = await postCustomComponentUpdate(
      code,
      name,
      data.node?.template[name]?.value
    )
      .then((res) => {
        console.log("res", res);
        if (res.status === 200 && data.node?.template) {
          return res.data.template;
        }
      })
      .catch((error) => {
        throw error;
      });
    return newTemplate;
  } catch (error) {
    console.error("Error occurred while updating the node:", error);
    let errorType = error as ResponseErrorTypeAPI;
    throw errorType;
  }
};

export const throttledHandleUpdateValues = throttle(handleUpdateValues, 10);
