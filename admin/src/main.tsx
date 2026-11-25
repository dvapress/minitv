import React, { useEffect } from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { ConfigProvider, theme as antdTheme } from "antd";
import zhCN from "antd/locale/zh_CN";
import "./index.css";
import App from "./App";

function AdminRoot() {
  useEffect(() => {
    document.documentElement.dataset.theme = "light";
  }, []);

  return (
    <ConfigProvider
      locale={zhCN}
      theme={{
        algorithm: antdTheme.defaultAlgorithm,
        token: {
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
            bodyBg: "#FFFBF7",
            headerBg: "#FFFFFF",
            siderBg: "#FFFFFF",
          },
          Menu: {
            itemBg: "transparent",
            itemSelectedBg: "rgba(234, 88, 12, 0.10)",
            itemSelectedColor: "#EA580C",
            itemHoverBg: "rgba(28, 25, 23, 0.04)",
            itemBorderRadius: 8,
          },
          Table: {
            headerBg: "#FAF5F0",
            rowHoverBg: "#FFF7ED",
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
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <AdminRoot />
  </React.StrictMode>,
);
