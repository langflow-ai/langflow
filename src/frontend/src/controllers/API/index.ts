import { AxiosResponse } from "axios";
import { ReactFlowJsonObject } from "reactflow";
import { api } from "../../controllers/API/api";
import { APIObjectType, sendAllProps } from "../../types/api/index";
import { FlowStyleType, FlowType } from "../../types/flow";
import {
  APIClassType,
  BuildStatusTypeAPI,
  InitTypeAPI,
  PromptTypeAPI,
  UploadFileTypeAPI,
  errorsTypeAPI,
} from "./../../types/api/index";

/**
 * Fetches all objects from the API endpoint.
 *
 * @returns {Promise<AxiosResponse<APIObjectType>>} A promise that resolves to an AxiosResponse containing all the objects.
 */
export async function getAll(): Promise<AxiosResponse<APIObjectType>> {
  return await api.get(`/api/v1/all`);
}

const GITHUB_API_URL = "https://api.github.com";

export async function getRepoStars(owner, repo) {
  try {
    const response = await api.get(`${GITHUB_API_URL}/repos/${owner}/${repo}`);
    return response.data.stargazers_count;
  } catch (error) {
    console.error("Error fetching repository data:", error);
    return null;
  }
}

/**
 * Sends data to the API for prediction.
 *
 * @param {sendAllProps} data - The data to be sent to the API.
 * @returns {AxiosResponse<any>} The API response.
 */
export async function sendAll(data: sendAllProps) {
  return await api.post(`/api/v1/predict`, data);
}

export async function postValidateCode(
  code: string
): Promise<AxiosResponse<errorsTypeAPI>> {
  return await api.post("/api/v1/validate/code", { code });
}

/**
 * Checks the prompt for the code block by sending it to an API endpoint.
 * @param {string} name - The name of the field to check.
 * @param {string} template - The template string of the prompt to check.
 * @param {APIClassType} frontend_node - The frontend node to check.
 * @returns {Promise<AxiosResponse<PromptTypeAPI>>} A promise that resolves to an AxiosResponse containing the validation results.
 */
export async function postValidatePrompt(
  name: string,
  template: string,
  frontend_node: APIClassType
): Promise<AxiosResponse<PromptTypeAPI>> {
  return await api.post("/api/v1/validate/prompt", {
    name: name,
    template: template,
    frontend_node: frontend_node,
  });
}

/**
 * Fetches a list of JSON files from a GitHub repository and returns their contents as an array of FlowType objects.
 *
 * @returns {Promise<FlowType[]>} A promise that resolves to an array of FlowType objects.
 */
export async function getExamples(): Promise<FlowType[]> {
  const url =
    "https://api.github.com/repos/logspace-ai/langflow_examples/contents/examples?ref=main";
  const response = await api.get(url);

  const jsonFiles = response.data.filter((file: any) => {
    return file.name.endsWith(".json");
  });

  const contentsPromises = jsonFiles.map(async (file: any) => {
    const contentResponse = await api.get(file.download_url);
    return contentResponse.data;
  });

  return await Promise.all(contentsPromises);
}

/**
 * Saves a new flow to the database.
 *
 * @param {FlowType} newFlow - The flow data to save.
 * @returns {Promise<any>} The saved flow data.
 * @throws Will throw an error if saving fails.
 */
export async function saveFlowToDatabase(newFlow: {
  name: string;
  id: string;
  data: ReactFlowJsonObject;
  description: string;
  style?: FlowStyleType;
}): Promise<FlowType> {
  try {
    const response = await api.post("/api/v1/flows/", {
      name: newFlow.name,
      data: newFlow.data,
      description: newFlow.description,
    });

    if (response.status !== 201) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    return response.data;
  } catch (error) {
    console.error(error);
    throw error;
  }
}
/**
 * Updates an existing flow in the database.
 *
 * @param {FlowType} updatedFlow - The updated flow data.
 * @returns {Promise<any>} The updated flow data.
 * @throws Will throw an error if the update fails.
 */
export async function updateFlowInDatabase(
  updatedFlow: FlowType
): Promise<FlowType> {
  try {
    const response = await api.patch(`/api/v1/flows/${updatedFlow.id}`, {
      name: updatedFlow.name,
      data: updatedFlow.data,
      description: updatedFlow.description,
    });

    if (response.status !== 200) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    return response.data;
  } catch (error) {
    console.error(error);
    throw error;
  }
}

/**
 * Reads all flows from the database.
 *
 * @returns {Promise<any>} The flows data.
 * @throws Will throw an error if reading fails.
 */
export async function readFlowsFromDatabase() {
  try {
    const response = await api.get("/api/v1/flows/");
    if (response.status !== 200) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    return response.data;
  } catch (error) {
    console.error(error);
    throw error;
  }
}

export async function downloadFlowsFromDatabase() {
  try {
    const response = await api.get("/api/v1/flows/download/");
    if (response.status !== 200) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    return response.data;
  } catch (error) {
    console.error(error);
    throw error;
  }
}

export async function uploadFlowsToDatabase(flows) {
  try {
    const response = await api.post(`/api/v1/flows/upload/`, flows);

    if (response.status !== 201) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    return response.data;
  } catch (error) {
    console.error(error);
    throw error;
  }
}

/**
 * Deletes a flow from the database.
 *
 * @param {string} flowId - The ID of the flow to delete.
 * @returns {Promise<any>} The deleted flow data.
 * @throws Will throw an error if deletion fails.
 */
export async function deleteFlowFromDatabase(flowId: string) {
  try {
    const response = await api.delete(`/api/v1/flows/${flowId}`);
    if (response.status !== 200) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    return response.data;
  } catch (error) {
    console.error(error);
    throw error;
  }
}

/**
 * Fetches a flow from the database by ID.
 *
 * @param {number} flowId - The ID of the flow to fetch.
 * @returns {Promise<any>} The flow data.
 * @throws Will throw an error if fetching fails.
 */
export async function getFlowFromDatabase(flowId: number) {
  try {
    const response = await api.get(`/api/v1/flows/${flowId}`);
    if (response.status !== 200) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    return response.data;
  } catch (error) {
    console.error(error);
    throw error;
  }
}

/**
 * Fetches flow styles from the database.
 *
 * @returns {Promise<any>} The flow styles data.
 * @throws Will throw an error if fetching fails.
 */
export async function getFlowStylesFromDatabase() {
  try {
    const response = await api.get("/api/v1/flow_styles/");
    if (response.status !== 200) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    return response.data;
  } catch (error) {
    console.error(error);
    throw error;
  }
}

/**
 * Saves a new flow style to the database.
 *
 * @param {FlowStyleType} flowStyle - The flow style data to save.
 * @returns {Promise<any>} The saved flow style data.
 * @throws Will throw an error if saving fails.
 */
export async function saveFlowStyleToDatabase(flowStyle: FlowStyleType) {
  try {
    const response = await api.post("/api/v1/flow_styles/", flowStyle, {
      headers: {
        accept: "application/json",
        "Content-Type": "application/json",
      },
    });

    if (response.status !== 201) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    return response.data;
  } catch (error) {
    console.error(error);
    throw error;
  }
}

/**
 * Fetches the version of the API.
 *
 * @returns {Promise<AxiosResponse<any>>} A promise that resolves to an AxiosResponse containing the version information.
 */
export async function getVersion() {
  const respnose = await api.get("/api/v1/version");
  return respnose.data;
}

/**
 * Fetches the health status of the API.
 *
 * @returns {Promise<AxiosResponse<any>>} A promise that resolves to an AxiosResponse containing the health status.
 */
export async function getHealth() {
  return await api.get("/health"); // Health is the only endpoint that doesn't require /api/v1
}

/**
 * Fetches the build status of a flow.
 * @param {string} flowId - The ID of the flow to fetch the build status for.
 * @returns {Promise<BuildStatusTypeAPI>} A promise that resolves to an AxiosResponse containing the build status.
 *
 */
export async function getBuildStatus(
  flowId: string
): Promise<BuildStatusTypeAPI> {
  return await api.get(`/api/v1/build/${flowId}/status`);
}

//docs for postbuildinit
/**
 * Posts the build init of a flow.
 * @param {string} flowId - The ID of the flow to fetch the build status for.
 * @returns {Promise<InitTypeAPI>} A promise that resolves to an AxiosResponse containing the build status.
 *
 */
export async function postBuildInit(
  flow: FlowType
): Promise<AxiosResponse<InitTypeAPI>> {
  return await api.post(`/api/v1/build/init/${flow.id}`, flow);
}

// fetch(`/upload/${id}`, {
//   method: "POST",
//   body: formData,
// });
/**
 * Uploads a file to the server.
 * @param {File} file - The file to upload.
 * @param {string} id - The ID of the flow to upload the file to.
 */
export async function uploadFile(
  file: File,
  id: string
): Promise<AxiosResponse<UploadFileTypeAPI>> {
  const formData = new FormData();
  formData.append("file", file);
  return await api.post(`/api/v1/upload/${id}`, formData);
}

export async function postCustomComponent(
  code: string,
  apiClass: APIClassType
): Promise<AxiosResponse<APIClassType>> {
  return await api.post(`/api/v1/custom_component`, { code });
}
