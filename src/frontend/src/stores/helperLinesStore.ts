import { create } from "zustand";
import type { HelperLinesState } from "@/pages/FlowPage/components/PageComponent/helpers/helper-lines";

type HelperLinesStore = {
  helperLines: HelperLinesState;
  setHelperLines: (helperLines: HelperLinesState) => void;
};

export const useHelperLinesStore = create<HelperLinesStore>((set) => ({
  helperLines: {},
  setHelperLines: (helperLines) => set({ helperLines }),
}));

export default useHelperLinesStore;
