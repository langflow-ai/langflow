import { BASE_URL_API, PROXY_TARGET } from "@/customization/config-constants";
import { ResponseErrorDetailAPI, useMutationFunctionType } from "@/types/api";
import { UseMutationResult } from "@tanstack/react-query";
import { useMemo, useRef } from "react";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IPostVoiceParams {
  flowId: string;
}

interface IPostVoicePayload {
  audio: Blob;
  useWebSocket?: boolean;
}

interface VoiceResponseType {
  text?: string;
  status: string;
  error?: string;
}

export const usePostVoice: useMutationFunctionType<
  IPostVoiceParams,
  IPostVoicePayload,
  VoiceResponseType,
  ResponseErrorDetailAPI
> = ({ flowId }, options?) => {
  const { mutate } = UseRequestProcessor();
  const wsRef = useRef<WebSocket | null>(null);

  const targetUrl = useMemo(() => {
    const httpUrl =
      process.env.VITE_PROXY_TARGET || "localhost:7860" || PROXY_TARGET;
    const cleanUrl = httpUrl.replace(/^https?:\/\//, "");
    return cleanUrl;
  }, []);

  const postVoiceFn = async (
    payload: IPostVoicePayload,
  ): Promise<VoiceResponseType> => {
    if (payload.useWebSocket) {
      return new Promise((resolve, reject) => {
        try {
          const url = `ws://${targetUrl}/api/v1/voice/ws/${flowId}`;

          if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
            wsRef.current.close();
          }

          wsRef.current = new WebSocket(
            `ws://${process.env.BACKEND_URL}/voice/ws/${flowId}`,
          );

          wsRef.current.onopen = () => {
            if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
              wsRef.current.send(payload.audio);
            }
          };

          wsRef.current.onmessage = (event) => {
            try {
              const data = JSON.parse(event.data);
              resolve(data);
            } catch (error) {
              reject({
                status: "error",
                error: "Failed to parse WebSocket response",
              });
            }
          };

          wsRef.current.onerror = (error) => {
            console.error("WebSocket Error:", error);
            reject({ status: "error", error: "WebSocket connection error" });
          };

          wsRef.current.onclose = () => {};
        } catch (error) {
          console.error("Failed to create WebSocket:", error);
          reject({
            status: "error",
            error: "Failed to create WebSocket connection",
          });
        }
      });
    }

    const formData = new FormData();
    formData.append("audio", payload.audio, "audio.wav");

    const response = await api.post<VoiceResponseType>(
      getURL("VOICE", { flowId }),
      formData,
      {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      },
    );

    return response.data;
  };

  const mutation: UseMutationResult<
    VoiceResponseType,
    ResponseErrorDetailAPI,
    IPostVoicePayload
  > = mutate(["usePostVoice", { flowId }], postVoiceFn, options);
  const closeWebSocket = () => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
  };

  return {
    ...mutation,
    closeWebSocket,
  };
};
