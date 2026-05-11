/**
 * @file Application entry point for the React frontend.
 *
 * Mounts the root <App /> component into the DOM inside React StrictMode.
 * This file is the Vite/Electron renderer entry — it bootstraps the entire
 * desktop UI and imports the global stylesheet.
 */
import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import "./styles.css";

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
