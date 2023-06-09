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
  return await axios.post("/validate/code", { code });
}

export async function checkPrompt(
  template: string
): Promise<AxiosResponse<PromptTypeAPI>> {
  return await axios.post("/validate/prompt", { template });
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

export async function saveFlowToDatabase(newFlow: FlowType) {
  try {
    const response = await fetch("/flows/", {
      method: "POST",
      headers: {
        accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        name: newFlow.name,
        data: newFlow.data,
        description: newFlow.description,
      }),
    });
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    return response.json();
  } catch (error) {
    console.error(error);
    throw error;
  }
}

export async function updateFlowInDatabase(updatedFlow: FlowType) {
  try {
    const response = await fetch(`/flows/${updatedFlow.id}`, {
      method: "PATCH", // Or "PATCH" depending on your backend API
      headers: {
        accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        name: updatedFlow.name,
        data: updatedFlow.data,
        description: updatedFlow.description,
      }),
    });
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    return response.json();
  } catch (error) {
    console.error(error);
    throw error;
  }
}

export async function readFlowsFromDatabase() {
  try {
    const response = await fetch("/flows/");
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    return response.json();
  } catch (error) {
    console.error(error);
    throw error;
  }
}

export async function deleteFlowFromDatabase(flowId: string) {
  try {
    const response = await fetch(`/flows/${flowId}`, {
      method: "DELETE",
    });
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    return response.json();
  } catch (error) {
    console.error(error);
    throw error;
  }
}

export async function getFlowFromDatabase(flowId: number) {
  try {
    const response = await fetch(`/flows/${flowId}`);
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    return response.json();
  } catch (error) {
    console.error(error);
    throw error;
  }
}

export async function getHealth() {
  return await axios.get("/health");
}
