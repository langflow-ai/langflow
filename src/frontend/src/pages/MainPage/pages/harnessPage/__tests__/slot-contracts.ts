import type { FlowContract } from "@/pages/MainPage/entities";
import declaredSlots from "./slot-contracts.json";

// Captured from the backend's built-in declarations, including binding model defaults.
export default declaredSlots as Record<
  keyof typeof declaredSlots,
  FlowContract
>;
