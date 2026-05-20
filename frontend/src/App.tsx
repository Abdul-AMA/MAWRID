import { useState } from "react";
import { BrowserRouter, useLocation } from "react-router-dom";
import ProcessPage from "@/pages/ProcessPage";
import SavedRecordsPage from "@/pages/SavedRecordsPage";
import ExperimentsPage from "@/pages/ExperimentsPage";
import OcrStagePage from "@/pages/OcrStagePage";
import VisionOcrPage from "@/pages/VisionOcrPage";
import GeminiOcrPage from "@/pages/GeminiOcrPage";
import GroqOcrPage from "@/pages/GroqOcrPage";
import OpenRouterOcrPage from "@/pages/OpenRouterOcrPage";
import TwoStagePage from "@/pages/TwoStagePage";
import AssistPage from "@/pages/AssistPage";
import ClaudeAssistPage from "@/pages/ClaudeAssistPage";
import OllamaAssistPage from "@/pages/OllamaAssistPage";
import Sidebar from "@/components/Sidebar";

type Dir = "rtl" | "ltr";

const PAGES = [
  { path: "/",             el: (dir: Dir) => <ProcessPage dir={dir} /> },
  { path: "/saved",        el: (dir: Dir) => <SavedRecordsPage dir={dir} /> },
  { path: "/experiments",  el: (dir: Dir) => <ExperimentsPage dir={dir} /> },
  { path: "/ocr",          el: (dir: Dir) => <OcrStagePage dir={dir} /> },
  { path: "/ocr-vision",   el: (dir: Dir) => <VisionOcrPage dir={dir} /> },
  { path: "/ocr-gemini",   el: (dir: Dir) => <GeminiOcrPage dir={dir} /> },
  { path: "/ocr-openrouter", el: (dir: Dir) => <OpenRouterOcrPage dir={dir} /> },
  { path: "/ocr-groq",     el: (dir: Dir) => <GroqOcrPage dir={dir} /> },
  { path: "/two-stage",   el: (dir: Dir) => <TwoStagePage dir={dir} /> },
  { path: "/assist",        el: (dir: Dir) => <AssistPage dir={dir} /> },
  { path: "/assist-claude", el: (dir: Dir) => <ClaudeAssistPage dir={dir} /> },
  { path: "/assist-ollama", el: (dir: Dir) => <OllamaAssistPage dir={dir} /> },
];

function AppInner({ dir, onToggleDir }: { dir: Dir; onToggleDir: () => void }) {
  const { pathname } = useLocation();

  return (
    <div className="flex h-screen overflow-hidden bg-background" dir={dir}>
      <Sidebar dir={dir} onToggleDir={onToggleDir} />
      <main className="flex-1 overflow-hidden">
        {PAGES.map(({ path, el }) => (
          <div key={path} style={{ display: pathname === path ? "contents" : "none" }}>
            {el(dir)}
          </div>
        ))}
      </main>
    </div>
  );
}

export default function App() {
  const [dir, setDir] = useState<Dir>("rtl");

  const toggleDir = () => {
    const next: Dir = dir === "rtl" ? "ltr" : "rtl";
    setDir(next);
    document.documentElement.setAttribute("dir", next);
    document.documentElement.setAttribute("lang", next === "rtl" ? "ar" : "en");
  };

  return (
    <BrowserRouter>
      <AppInner dir={dir} onToggleDir={toggleDir} />
    </BrowserRouter>
  );
}
