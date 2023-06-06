import { PromptTypeAPI, errorsTypeAPI } from "./../../types/api/index";
import { APIObjectType, sendAllProps } from "../../types/api/index";
import axios, { AxiosResponse } from "axios";
import { FlowType } from "../../types/flow";

export async function getAll(): Promise<AxiosResponse<APIObjectType>> {
  return await axios.get(`/all`);
}

export async function sendAll(data: sendAllProps) {
  return await axios.post(`/predict`, data);
}

export async function checkCode(
  code: string
): Promise<AxiosResponse<errorsTypeAPI>> {
  return await axios.post("api/v1/validate/code", { code });
}

export async function checkPrompt(
  template: string
): Promise<AxiosResponse<PromptTypeAPI>> {
  return await axios.post("api/v1/validate/prompt", { template });
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

  const contents = await Promise.all(contentsPromises);

  return contents;
}
