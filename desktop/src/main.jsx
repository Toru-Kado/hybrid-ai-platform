import React from "react";
import { createRoot } from "react-dom/client";
import { AuthProvider } from "./auth";
import AuthGate from "./components/AuthGate";
import App from "./App.jsx";
import "./styles.css";

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <AuthProvider>
      <AuthGate>
        <App />
      </AuthGate>
    </AuthProvider>
  </React.StrictMode>,
);
