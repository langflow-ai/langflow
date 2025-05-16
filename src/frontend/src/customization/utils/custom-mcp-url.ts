import { api } from "@/controllers/API/api";

export const customGetMCPUrl = (projectId: string) => {
  const apiHost = api.defaults.baseURL || window.location.origin;
  const apiUrl = `${apiHost}/api/v1/mcp/project/${projectId}/sse`;
  return apiUrl;
};
