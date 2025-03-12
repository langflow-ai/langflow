import { Actor } from "@/types/actors";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api";
import { getURL } from "../helpers/constants";

// Fetch actors with optional filters
export const useGetActors = (params?: {
  entity_type?: string;
  entity_id?: string;
  project_id?: string;
}) => {
  return useQuery({
    queryKey: ["actors", params],
    queryFn: async () => {
      const response = await api.get(`${getURL("ACTORS")}/`, { params });
      return response.data as Actor[];
    },
  });
};

// Get a specific actor by ID
export const useGetActor = (actorId?: string) => {
  return useQuery({
    queryKey: ["actor", actorId],
    queryFn: async () => {
      if (!actorId) return null;
      const response = await api.get(`${getURL("ACTORS")}/${actorId}`);
      return response.data as Actor;
    },
    enabled: !!actorId,
  });
};
