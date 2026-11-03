// Keep the worklet as a separately emitted JavaScript asset. AudioWorklet
// modules execute in their own global scope, so this URL must remain a real
// packaged file rather than an inlined data/blob URL.
import workletUrl from "./audio-worklet-processor.js?url&no-inline";

export { workletUrl };
