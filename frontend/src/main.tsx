import { StrictMode, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { Audience } from "./pages/Audience";
import { Home } from "./pages/Home";
import { Presenter } from "./pages/Presenter";
import "./styles.css";

function parse(hash: string): { page: "home" } | { page: "presenter" | "audience"; sid: string } {
  const m = hash.match(/^#\/s\/(ses_[0-9a-f]{12})(\/audience)?$/);
  if (!m) return { page: "home" };
  return { page: m[2] ? "audience" : "presenter", sid: m[1] };
}

function App() {
  const [route, setRoute] = useState(() => parse(location.hash));
  useEffect(() => {
    const h = () => setRoute(parse(location.hash));
    window.addEventListener("hashchange", h);
    return () => window.removeEventListener("hashchange", h);
  }, []);
  useEffect(() => {
    document.body.dataset.page = route.page;
  }, [route.page]);
  if (route.page === "presenter") return <Presenter key={route.sid} sid={route.sid} />;
  if (route.page === "audience") return <Audience key={route.sid} sid={route.sid} />;
  return <Home />;
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
