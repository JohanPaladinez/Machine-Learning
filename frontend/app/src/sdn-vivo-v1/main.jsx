import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "../index.css";
import "../App.css";
import "./panel.css";
import "./live.css";
import LiveRoot from "./LiveRoot.jsx";
createRoot(document.getElementById("root")).render(<StrictMode><LiveRoot /></StrictMode>);
