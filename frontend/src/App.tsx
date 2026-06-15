import { useState } from "react";
import { BrowserRouter, useLocation } from "react-router-dom";
import ManualFillPage from "@/pages/ManualFillPage";
import SavedRecordsPage from "@/pages/SavedRecordsPage";
import AssistEnPage from "@/pages/AssistEnPage";
import AssistClaudePage from "@/pages/AssistClaudePage";
import AssistClaudeHaikuPage from "@/pages/AssistClaudeHaikuPage";
import Sidebar from "@/components/Sidebar";
import { SchemaProvider } from "@/lib/schemaContext";

type Dir = "rtl" | "ltr";

const PAGES = [
  { path: "/",               el: (dir: Dir) => <ManualFillPage dir={dir} /> },
  { path: "/assist-en",      el: (dir: Dir) => <AssistEnPage dir={dir} /> },
  { path: "/assist-claude",       el: (dir: Dir) => <AssistClaudePage dir={dir} /> },
  { path: "/assist-claude-fast",  el: (dir: Dir) => <AssistClaudeHaikuPage dir={dir} /> },
  { path: "/saved",          el: (dir: Dir) => <SavedRecordsPage dir={dir} /> },
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
    <SchemaProvider>
      <BrowserRouter>
        <AppInner dir={dir} onToggleDir={toggleDir} />
      </BrowserRouter>
    </SchemaProvider>
  );
}
