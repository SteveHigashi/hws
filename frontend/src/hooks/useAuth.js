import { create } from "zustand";
import { persist } from "zustand/middleware";
import api from "../utils/api";

export const useAuthStore = create(
  persist(
    (set) => ({
      token: null,
      role: null,
      email: null,
      login: async (email, password, options = {}) => {
        const { remember = true } = options;
        const form = new URLSearchParams({ username: email, password });
        const { data } = await api.post("/auth/login", form);
        set({ token: data.access_token, role: data.role, email });
        api.defaults.headers.common["Authorization"] = `Bearer ${data.access_token}`;
        if (remember) {
          localStorage.setItem("ha-login-email", email);
        } else {
          localStorage.removeItem("ha-login-email");
          localStorage.removeItem("ha-auth");
        }
        return data;
      },
      logout: () => {
        set({ token: null, role: null, email: null });
        delete api.defaults.headers.common["Authorization"];
      },
    }),
    { name: "ha-auth" }
  )
);
