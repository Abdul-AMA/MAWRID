import { NavLink } from "react-router-dom";
import { Sparkles, Archive, Globe, ScanText, Eye, Zap, Cloud, GitCompare, WandSparkles, Bot, Cpu } from "lucide-react";
import { cn } from "@/lib/utils";

interface Props {
  dir: "rtl" | "ltr";
  onToggleDir: () => void;
}

const NAV = [
  { to: "/",           end: true,  icon: Sparkles, label: { ar: "المعالجة",        en: "Process" } },
  { to: "/saved",      end: false, icon: Archive,  label: { ar: "السجلات",         en: "Saved Records" } },
  { to: "/ocr",        end: false, icon: ScanText, label: { ar: "مرحلة OCR",       en: "OCR Stage" } },
  { to: "/ocr-vision",      end: false, icon: Eye,   label: { ar: "OCR كلود",         en: "Claude OCR" } },
  { to: "/ocr-gemini",      end: false, icon: Zap,   label: { ar: "OCR جيميني",      en: "Gemini OCR" } },
  { to: "/ocr-openrouter",  end: false, icon: Cloud, label: { ar: "OCR أوبن راوتر",  en: "OpenRouter OCR" } },
  { to: "/ocr-groq",       end: false, icon: Zap,    label: { ar: "OCR جروك",          en: "Groq OCR" } },
  { to: "/two-stage",      end: false, icon: GitCompare,    label: { ar: "مرحلتان",        en: "Two-Stage" } },
  { to: "/assist",         end: false, icon: WandSparkles, label: { ar: "مساعد — Groq",   en: "Assist (Groq)" } },
  { to: "/assist-claude",  end: false, icon: Bot,          label: { ar: "مساعد — كلود",   en: "Assist (Claude)" } },
  { to: "/assist-ollama",  end: false, icon: Cpu,          label: { ar: "مساعد — أولاما", en: "Assist (Ollama)" } },
];

export default function Sidebar({ dir, onToggleDir }: Props) {
  return (
    <aside
      className={cn(
        "h-screen w-52 shrink-0 flex flex-col bg-white sticky top-0 z-30",
        dir === "rtl" ? "border-l" : "border-r"
      )}
    >
      {/* Logo */}
      <div className="h-14 flex items-center px-5 border-b">
        <span className="font-bold text-lg tracking-tight text-primary">
          {dir === "rtl" ? "مورد" : "MAWRID"}
        </span>
      </div>

      {/* Nav items */}
      <nav className="flex-1 p-3 space-y-0.5">
        {NAV.map(({ to, end, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors",
                isActive
                  ? "bg-primary/10 text-primary"
                  : "text-muted-foreground hover:text-foreground hover:bg-muted"
              )
            }
          >
            <Icon className="w-4 h-4 shrink-0" />
            {dir === "rtl" ? label.ar : label.en}
          </NavLink>
        ))}
      </nav>

      {/* Language toggle */}
      <div className="p-3 border-t">
        <button
          onClick={onToggleDir}
          className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
        >
          <Globe className="w-4 h-4 shrink-0" />
          {dir === "rtl" ? "English" : "العربية"}
        </button>
      </div>
    </aside>
  );
}
