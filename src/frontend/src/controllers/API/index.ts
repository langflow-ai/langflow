import { PromptTypeAPI, errorsTypeAPI } from "./../../types/api/index";
import { APIObjectType, sendAllProps } from "../../types/api/index";
import axios, { AxiosResponse } from "axios";
import { FlowType } from "../../types/flow";

// when serving with static files
// We need to add /api/v1/ to the url in the axios calls

/**
 * Retrieves all data from the API.
 * @returns {Promise<AxiosResponse<APIObjectType>>} A promise that resolves to an AxiosResponse object containing the API data.
 */
export async function getAll(): Promise<AxiosResponse<APIObjectType>> {
  return await axios.get(`/api/v1/all`);
}

export async function sendAll(data: sendAllProps) {
  return await axios.post(`/api/v1/predict`, data);
}

export async function postValidateCode(
  code: string
): Promise<AxiosResponse<errorsTypeAPI>> {
  return await axios.post("/api/v1/validate/code", { code });
}

export async function postValidateNode(
  nodeId: string,
  data: any
): Promise<AxiosResponse<string>> {
  return await axios.post(`/api/v1/validate/node/${nodeId}`, { data });
}

export async function checkPrompt(
  template: string
): Promise<AxiosResponse<PromptTypeAPI>> {
  return await axios.post("/api/v1/validate/prompt", { template });
}

/**
 * Retrieves the version of the API.
 * @returns {Promise<AxiosResponse<{ version: string }>>} A promise that resolves to an AxiosResponse object containing the API version.
 * @example
 * const response = await getVersion();
 * console.log(response.data.version);
 * // 0.1.0
 */
export async function getVersion(): Promise<
  AxiosResponse<{ version: string }>
> {
  return await axios.get("/api/v1/version");
}

export async function getExamples(): Promise<FlowType[]> {
  const url =
    "https://api.github.com/repos/logspace-ai/langflow_examples/contents/examples";
  const response = await axios.get(url);

  const jsonFiles = response.data.filter((file: any) => {
    return file.name.endsWith(".json");
  });

  const contentsPromises = jsonFiles.map(async (file: any) => {
    const contentResponse = await axios.get(file.download_url);
    return contentResponse.data;
  });

  return await Promise.all(contentsPromises);
}
