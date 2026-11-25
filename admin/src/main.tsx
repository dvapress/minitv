import React, { createContext, useContext, useEffect, useState } from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { ConfigProvider, theme as antdTheme } from "antd";
import zhCN from "antd/locale/zh_CN";
import "./index.css";
import App from "./App";

const THEME_KEY = "leapdrama_theme";

export type AdminThemeMode = "dark" | "light";

const AdminThemeContext = createContext<{
  mode: AdminThemeMode;
  toggleMode: () => void;
}>({
  mode: "dark",
  toggleMode: () => {},
});

export function useAdminTheme() {
  return useContext(AdminThemeContext);
}

function AdminRoot() {
  const [mode, setMode] = useState<AdminThemeMode>(() =>
    localStorage.getItem(THEME_KEY) === "light" ? "light" : "dark",
  );

  useEffect(() => {
    document.documentElement.dataset.theme = mode;
    localStorage.setItem(THEME_KEY, mode);
    const onStorage = (e: StorageEvent) => {
      if (e.key === THEME_KEY && (e.newValue === "light" || e.newValue === "dark")) {
        setMode(e.newValue);
      }
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, [mode]);

  const isDark = mode === "dark";
  const toggleMode = () => setMode((m) => (m === "dark" ? "light" : "dark"));

  return (
    <AdminThemeContext.Provider value={{ mode, toggleMode }}>
      <ConfigProvider
        locale={zhCN}
        theme={{
          algorithm: isDark ? antdTheme.darkAlgorithm : antdTheme.defaultAlgorithm,
          token: isDark
            ? {
                colorPrimary: "#F97316",
                colorInfo: "#F97316",
                colorWarning: "#FACC15",
                colorBgBase: "#16110E",
                colorBgLayout: "#16110E",
                colorBgContainer: "#241C18",
                colorBgElevated: "#2D231D",
                colorBorder: "rgba(253, 248, 246, 0.12)",
                colorBorderSecondary: "rgba(253, 248, 246, 0.08)",
                colorTextBase: "#FDF8F6",
                colorTextSecondary: "#A8A29E",
                borderRadius: 10,
              }
            : {
                colorPrimary: "#EA580C",
                colorInfo: "#0D9488",
                colorWarning: "#D97706",
                colorBgBase: "#FFFBF7",
                colorBgLayout: "#FFFBF7",
                colorBgContainer: "#FFFFFF",
                colorBgElevated: "#FFFFFF",
                colorBorder: "rgba(28, 25, 23, 0.12)",
                colorBorderSecondary: "rgba(28, 25, 23, 0.08)",
                colorTextBase: "#1C1917",
                colorTextSecondary: "#57534E",
                borderRadius: 10,
              },
          components: {
            Layout: {
              bodyBg: isDark ? "#16110E" : "#FFFBF7",
              headerBg: isDark ? "#241C18" : "#FFFFFF",
              siderBg: isDark ? "#1D1612" : "#FFFFFF",
            },
            Menu: {
              itemBg: "transparent",
              itemSelectedBg: isDark ? "rgba(249, 115, 22, 0.16)" : "rgba(234, 88, 12, 0.10)",
              itemSelectedColor: isDark ? "#FB923C" : "#EA580C",
              itemHoverBg: isDark ? "rgba(253, 248, 246, 0.06)" : "rgba(28, 25, 23, 0.04)",
              itemBorderRadius: 8,
            },
            Table: {
              headerBg: isDark ? "#2B211C" : "#FAF5F0",
              rowHoverBg: isDark ? "rgba(249, 115, 22, 0.06)" : "#FFF7ED",
            },
            Card: {
              headerBg: "transparent",
            },
          },
        }}
      >
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </ConfigProvider>
    </AdminThemeContext.Provider>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <AdminRoot />
  </React.StrictMode>,
);
