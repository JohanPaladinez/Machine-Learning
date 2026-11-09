
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "../index.css";
import "../App.css";
import "../sdn-vivo-v1/panel.css";
import "../sdn-vivo-v1/live.css";
import SelectorRoot from "./SelectorRoot.jsx";

createRoot(document.getElementById("root")).render(
  <StrictMode><SelectorRoot /></StrictMode>
);
