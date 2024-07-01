import { cloneDeep } from "lodash";
import { TABS_ORDER } from "../../../constants/constants";

export default function getTabsOrder(
  isThereWH: boolean = false,
  isThereTweaks: boolean = false,
): string[] {
  const defaultOrder = cloneDeep(TABS_ORDER);
  if (isThereTweaks) {
    defaultOrder.push("tweaks");
  }
  if (isThereWH) {
    defaultOrder.splice(1, 0, "webhook curl");
  }
  return defaultOrder;
}
