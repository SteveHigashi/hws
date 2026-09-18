import { create } from "zustand";
import { persist } from "zustand/middleware";

export const useSiteStore = create(
  persist(
    (set) => ({
      sites: [],
      currentSiteId: null,
      setSites: (sites) => set({ sites }),
      setCurrentSite: (id) => set({ currentSiteId: id }),
    }),
    {
      name: "ha-site",
      partialize: (state) => ({ currentSiteId: state.currentSiteId }),
    }
  )
);
