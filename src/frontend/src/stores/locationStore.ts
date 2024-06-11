import { create } from "zustand";
import { LocationStoreType } from "../types/zustand/location";

export const useLocationStore = create<LocationStoreType>((set, get) => ({
  routeHistory: [],
  setRouteHistory: (location) => {
    let routeHistoryArray = get().routeHistory;
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
