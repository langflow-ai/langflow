import { create } from "zustand";
import type { LocationStoreType } from "../types/zustand/location";

export const useLocationStore = create<LocationStoreType>((set, get) => ({
  routeHistory: [],
  setRouteHistory: (location) => {
    const routeHistoryArray = get().routeHistory;
    routeHistoryArray.push(location);

    if (routeHistoryArray?.length > 100) {
      routeHistoryArray.shift();
      set({
        routeHistory: routeHistoryArray,
      });
    }

    set({
      routeHistory: routeHistoryArray,
    });
  },
}));
