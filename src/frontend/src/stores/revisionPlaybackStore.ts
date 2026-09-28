import { create } from "zustand";
import type { RecordedOperation } from "@/types/flow/revision";

/** The timeline entry being previewed, for stepping through its operations on the canvas. */
export type PlaybackEntry = {
  flowId: string;
  /** The revision before the entry's first operation: where playback starts. */
  fromRevision: number;
  /** The entry's last revision: what the preview shows and a restore returns to. */
  toRevision: number;
  operations: RecordedOperation[];
};

interface RevisionPlaybackState {
  entry: PlaybackEntry | null;
  setEntry: (entry: PlaybackEntry | null) => void;
}

const useRevisionPlaybackStore = create<RevisionPlaybackState>((set) => ({
  entry: null,
  setEntry: (entry) => set({ entry }),
}));

export default useRevisionPlaybackStore;
