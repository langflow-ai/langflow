export interface CustomProviderModelSchema {
  name: string;
  tool_calling: boolean;
}

export interface CustomProviderModelRead {
  id: string;
  provider_id: string;
  name: string;
  tool_calling: boolean;
}

export interface CustomProviderRead {
  id: string;
  user_id: string;
  name: string;
  base_url: string;
  models: CustomProviderModelRead[];
  created_at: string;
  updated_at: string;
}

export interface CustomProviderCreate {
  name: string;
  base_url: string;
  api_key: string;
  models: CustomProviderModelSchema[];
}

export interface CustomProviderUpdate {
  name?: string;
  base_url?: string;
  api_key?: string;
  models?: CustomProviderModelSchema[];
}

export interface DiscoverModelsResponse {
  models: string[];
  discovery_supported: boolean;
  error: string | null;
}
