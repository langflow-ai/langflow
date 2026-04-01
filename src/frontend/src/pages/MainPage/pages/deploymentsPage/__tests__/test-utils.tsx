import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { BrowserRouter } from "react-router-dom";
import type { Deployment, ProviderAccount } from "../types";

/**
 * Creates a test wrapper with React Query and Router providers
 */
export const createTestWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>{children}</BrowserRouter>
    </QueryClientProvider>
  );
};

export const mockDeployment: Deployment = {
  id: "deploy-1",
  name: "My Agent",
  description: "A test agent",
  type: "agent",
  created_at: "2025-01-01T00:00:00Z",
  updated_at: "2025-01-02T00:00:00Z",
  provider_data: {
    llm: "ibm/granite-3-8b-instruct",
    resource_key: "my-agent-key",
  },
  resource_key: "my-agent-key",
  attached_count: 2,
};

export const mockDeploymentNoLlm: Deployment = {
  id: "deploy-2",
  name: "Blank Agent",
  description: null,
  type: "agent",
  created_at: "2025-01-01T00:00:00Z",
  updated_at: "2025-01-02T00:00:00Z",
  provider_data: null,
  resource_key: "blank-agent-key",
  attached_count: 0,
};

export const mockProviderAccount: ProviderAccount = {
  id: "provider-1",
  name: "Production",
  provider_tenant_id: null,
  provider_key: "watsonx-orchestrate",
  provider_url: "https://api.example.com",
  created_at: "2025-01-01T00:00:00Z",
  updated_at: "2025-01-02T00:00:00Z",
};

export const setupAlertStoreMock = () => {
  const mockSetSuccessData = jest.fn();
  const mockSetErrorData = jest.fn();
  return { mockSetSuccessData, mockSetErrorData };
};
