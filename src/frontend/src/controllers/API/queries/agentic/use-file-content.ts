/**
 * TanStack Query hook that fetches a sandboxed file's text content.
 *
 * Backed by ``GET /api/v1/agentic/files?path=...`` — the same endpoint
 * ``assistant-file-card`` uses for downloads (without the ``download``
 * flag, so the response is ``text/plain; charset=utf-8``).
 *
 * Uses the project's ``api`` axios instance (not raw ``fetch``) so the
 * request rides on the same auth interceptor as the rest of the app —
 * cookies, 401-refresh, and custom headers are all handled uniformly.
 */

import { useQuery } from "@tanstack/react-query";

import { api } from "../../api";
import { getURL } from "../../helpers/constants";

interface UseFileContentOptions {
  enabled?: boolean;
}

export function useFileContent(
  path: string,
  options: UseFileContentOptions = {},
) {
  const enabled = options.enabled ?? true;

  return useQuery<string, Error>({
    queryKey: ["agentic-file", path],
    enabled: enabled && Boolean(path),
    staleTime: Infinity,
    queryFn: async (): Promise<string> => {
      const url = `${getURL("AGENTIC_FILES")}?${new URLSearchParams({ path }).toString()}`;
      try {
        // responseType: 'text' so axios doesn't try to JSON-parse the
        // text/plain body (which can throw on plain markdown content).
        const response = await api.get<string>(url, { responseType: "text" });
        return response.data;
      } catch (err) {
        const status =
          (err as { response?: { status?: number } } | undefined)?.response
            ?.status ?? "?";
        console.error("[useFileContent] axios get failed", status, url, err);
        throw new Error(`Failed to load file (HTTP ${status})`);
      }
    },
  });
}
