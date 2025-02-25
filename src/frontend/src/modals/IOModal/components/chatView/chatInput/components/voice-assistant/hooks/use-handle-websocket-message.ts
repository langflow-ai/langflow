import { BuildStatus } from "@/constants/enums";
import { Edge } from "@xyflow/react";
import { base64ToFloat32Array } from "../utils";

export const useHandleWebsocketMessage = (
  event: MessageEvent,
  interruptPlayback: () => void,
  audioContextRef: React.MutableRefObject<AudioContext | null>,
  audioQueueRef: React.MutableRefObject<AudioBuffer[]>,
  isPlayingRef: React.MutableRefObject<boolean>,
  playNextAudioChunk: () => void,
  setIsBuilding: (isBuilding: boolean) => void,
  revertBuiltStatusFromBuilding: () => void,
  clearEdgesRunningByNodes: () => void,
  setMessage: React.Dispatch<React.SetStateAction<string>>,
  edges,
  setStatus: React.Dispatch<React.SetStateAction<string>>,
  setShowApiKeyModal: React.Dispatch<React.SetStateAction<boolean>>,
  messagesStore,
  setEdges,
  addDataToFlowPool: (data: any, nodeId: string) => void,
  updateEdgesRunningByNodes: (nodeIds: string[], isRunning: boolean) => void,
  updateBuildStatus: (nodeIds: string[], status: BuildStatus) => void,
) => {
  const data = JSON.parse(event.data);

  switch (data.type) {
    case "response.content_part.added":
      if (data.part?.type === "text" && data.part.text) {
        setMessage((prev) => prev + data.part.text);
      }
      break;

    case "response.cancelled":
      console.log("response.cancelled");
      // If the server acknowledges our response.cancel, forcibly stop leftover audio
      interruptPlayback();
      break;

    case "response.audio.delta":
      console.log("response.audio.delta");
      if (data.delta && audioContextRef.current) {
        try {
          const float32Data = base64ToFloat32Array(data.delta);
          const audioBuffer = audioContextRef.current.createBuffer(
            2,
            float32Data.length,
            24000,
          );
          audioBuffer.copyToChannel(float32Data, 0);
          audioBuffer.copyToChannel(float32Data, 1);
          audioQueueRef.current.push(audioBuffer);
          if (!isPlayingRef.current) {
            playNextAudioChunk();
          }
        } catch (error) {
          console.error("Error processing audio response:", error);
        }
      }
      break;

    case "flow.build.progress":
      console.log("flow.build.progress", data);
      const buildData = data.data;
      switch (buildData.event) {
        case "start":
          setIsBuilding(true);
          break;

        case "start_vertex":
          updateBuildStatus([buildData.vertex_id], BuildStatus.BUILDING);
          const newEdges = edges.map((edge) => {
            if (buildData.vertex_id === edge.data?.targetHandle?.id) {
              edge.animated = true;
              edge.className = "running";
            }
            return edge;
          });
          setEdges(newEdges);
          break;

        case "end_vertex":
          updateBuildStatus([buildData.vertex_id], BuildStatus.BUILT);
          addDataToFlowPool(
            {
              ...buildData.data.build_data,
              run_id: buildData.run_id,
              id: buildData.vertex_id,
              valid: true,
            },
            buildData.vertex_id,
          );
          updateEdgesRunningByNodes([buildData.vertex_id], false);
          break;

        case "error":
          updateBuildStatus([buildData.vertex_id], BuildStatus.ERROR);
          updateEdgesRunningByNodes([buildData.vertex_id], false);
          break;

        case "end":
          setIsBuilding(false);
          revertBuiltStatusFromBuilding();
          clearEdgesRunningByNodes();
          break;

        case "add_message":
          messagesStore.addMessage(buildData.data);
          break;
      }
      break;

    case "error":
      console.error("Server error:", data.error);
      if (data.code === "api_key_missing") {
        setShowApiKeyModal(true);
      }
      if (
        data.error.message === "Cancellation failed: no active response found"
      ) {
        interruptPlayback();
      } else {
        setStatus("Error: " + data.error);
      }
      break;
  }
};
