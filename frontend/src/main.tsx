import React from "react";
import ReactDOM from "react-dom/client";
import { Provider } from "react-redux";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { store } from "./store";
import SearchPage from "./pages/SearchPage";
import EnterprisePage from "./pages/EnterprisePage";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <Provider store={store}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<SearchPage />} />
          <Route path="/enterprise/:bce" element={<EnterprisePage />} />
        </Routes>
      </BrowserRouter>
    </Provider>
  </React.StrictMode>
);
