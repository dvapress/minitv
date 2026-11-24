import React, { useEffect, useState } from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { ConfigProvider, theme as antdTheme } from "antd";
import zhCN from "antd/locale/zh_CN";
import "./index.css";
import App from "./App";

const THEME_KEY = "leapdrama_theme";

function AdminRoot() {
  const [mode, setMode] = useState<"dark" | "light">(() =>
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

  return (
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
              colorBgContainer: "#241C18",
              colorTextBase: "#FDF8F6",
              borderRadius: 8,
            }
          : {
              colorPrimary: "#EA580C",
              colorInfo: "#0D9488",
              colorBgBase: "#FFFBF7",
              colorBgContainer: "#FFFFFF",
              colorTextBase: "#1C1917",
              borderRadius: 8,
            },
      }}
    >
      <button
        type="button"
        onClick={() => setMode((m) => (m === "dark" ? "light" : "dark"))}
        title={isDark ? "切换浅色模式" : "切换深色模式"}
        style={{
          position: "fixed",
          right: 18,
          bottom: 18,
          zIndex: 1000,
          width: 40,
          height: 40,
          borderRadius: 20,
          border: "1px solid rgba(249,115,22,0.45)",
          background: isDark ? "#241C18" : "#FFFFFF",
          color: isDark ? "#FACC15" : "#EA580C",
          fontSize: 18,
          cursor: "pointer",
          boxShadow: "0 6px 18px rgba(0,0,0,0.28)",
        }}
      >
        {isDark ? "☀" : "☾"}
      </button>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </ConfigProvider>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <AdminRoot />
  </React.StrictMode>,
);
