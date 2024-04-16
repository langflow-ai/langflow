import { debounce } from "lodash";
import { SAVE_DEBOUNCE_TIME } from "../constants/constants";
import { postCustomComponentUpdate, postValidatePrompt } from "../controllers/API";
import { ResponseErrorTypeAPI } from "../types/api";
import { NodeDataType } from "../types/flow";
import { BUG_ALERT, PROMPT_ERROR_ALERT } from "../constants/alerts_constants";

export const handleUpdateValues = async (name: string, data: NodeDataType) => {
  const code = data.node?.template["code"]?.value;
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
    let newTemplate = await postCustomComponentUpdate(
      code,
      template,
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

export const debouncedHandleUpdateValues = debounce(
  handleUpdateValues,
  SAVE_DEBOUNCE_TIME
);

export function validatePrompt(value, field_name, nodeClass, setNodeClass): Promise<string[]> {
  //nodeClass is always null on tweaks
  return new Promise((resolve, reject) => {
    postValidatePrompt(field_name, value, nodeClass!)
    .then((apiReturn) => {
      // if field_name is an empty string, then we need to set it
      // to the first key of the custom_fields object
      if (field_name === "") {
        field_name = Array.isArray(
          apiReturn.data?.frontend_node?.custom_fields?.[""]
        )
          ? apiReturn.data?.frontend_node?.custom_fields?.[""][0] ?? ""
          : apiReturn.data?.frontend_node?.custom_fields?.[""] ?? "";
      }
      if (apiReturn.data) {
        let inputVariables = apiReturn.data.input_variables ?? [];
        if (
          JSON.stringify(apiReturn.data?.frontend_node) !== JSON.stringify({})
        ) {
          if (setNodeClass)
            setNodeClass(apiReturn.data?.frontend_node, value);
          resolve(inputVariables);
        }
      } else {
        reject({
          title: BUG_ALERT,
        });
      }
    })
    .catch((error) => {
      reject({
        title: PROMPT_ERROR_ALERT,
        list: [error.response.data.detail ?? ""],
      });
    });
  })
}
