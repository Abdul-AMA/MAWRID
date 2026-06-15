import { useState, useRef } from "react";
import { NavLink } from "react-router-dom";
import { PenLine, Archive, Globe, Zap, Sparkles, GripVertical, DatabaseZap } from "lucide-react";
import { cn } from "@/lib/utils";
import { useSchemaCtx } from "@/lib/schemaContext";
import SchemaSettings from "./SchemaSettings";

interface Props {
  dir: "rtl" | "ltr";
  onToggleDir: () => void;
}

const NAV = [
  { to: "/",             end: true,  icon: PenLine,   label: { ar: "وثيقة جديدة", en: "New Document" }, badge: null },
  { to: "/assist-en",         end: false, icon: Zap,      label: { ar: "Groq",         en: "Groq"        }, badge: { text: "Groq",   color: "bg-orange-100 text-orange-600" } },
  { to: "/assist-claude",     end: false, icon: Sparkles, label: { ar: "Claude",       en: "Claude"      }, badge: { text: "Sonnet", color: "bg-violet-100 text-violet-600" } },
  { to: "/assist-claude-fast",end: false, icon: Sparkles, label: { ar: "Claude سريع",  en: "Claude Fast" }, badge: { text: "Haiku",  color: "bg-teal-100 text-teal-600"   } },
  { to: "/saved",        end: false, icon: Archive,   label: { ar: "السجلات",      en: "Records"      }, badge: null },
];

const STORAGE_KEY = "mawrid-sidebar-order";

function loadOrder(): typeof NAV {
  try {
    const saved: string[] = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "");
    if (!Array.isArray(saved)) return NAV;
    const ordered = saved
      .map(to => NAV.find(n => n.to === to))
      .filter(Boolean) as typeof NAV;
    // keep any new items not yet in storage
    const missing = NAV.filter(n => !saved.includes(n.to));
    return [...ordered, ...missing];
  } catch {
    return NAV;
  }
}

export default function Sidebar({ dir, onToggleDir }: Props) {
  const [items, setItems] = useState<typeof NAV>(loadOrder);
  const [dragOver, setDragOver] = useState<number | null>(null);
  const dragIndex = useRef<number | null>(null);
  const [showSchemaSettings, setShowSchemaSettings] = useState(false);
  const { source } = useSchemaCtx();

  const handleDragStart = (i: number) => {
    dragIndex.current = i;
  };

  const handleDragOver = (e: React.DragEvent, i: number) => {
    e.preventDefault();
    if (dragIndex.current === null || dragIndex.current === i) return;
    setDragOver(i);
    const next = [...items];
    const [moved] = next.splice(dragIndex.current, 1);
    next.splice(i, 0, moved);
    dragIndex.current = i;
    setItems(next);
  };

  const handleDragEnd = () => {
    dragIndex.current = null;
    setDragOver(null);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(items.map(n => n.to)));
  };

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
        {items.map(({ to, end, icon: Icon, label, badge }, i) => (
          <div
            key={to}
            draggable
            onDragStart={() => handleDragStart(i)}
            onDragOver={e => handleDragOver(e, i)}
            onDragEnd={handleDragEnd}
            className={cn(
              "group flex items-center rounded-lg transition-all duration-150",
              dragOver === i && dragIndex.current !== i ? "ring-2 ring-primary/30 bg-primary/5" : ""
            )}
          >
            {/* Drag handle */}
            <div className="flex items-center justify-center w-5 shrink-0 cursor-grab active:cursor-grabbing opacity-0 group-hover:opacity-40 transition-opacity ms-1">
              <GripVertical className="w-3.5 h-3.5 text-muted-foreground" />
            </div>

            <NavLink
              to={to}
              end={end}
              className={({ isActive }) =>
                cn(
                  "flex flex-1 items-center gap-2 px-2 py-2.5 rounded-lg text-sm font-medium transition-colors min-w-0",
                  isActive
                    ? "bg-primary/10 text-primary"
                    : "text-muted-foreground hover:text-foreground hover:bg-muted"
                )
              }
            >
              <Icon className="w-4 h-4 shrink-0" />
              <span className="truncate flex-1">{dir === "rtl" ? label.ar : label.en}</span>
              {badge && (
                <span className={cn("text-[10px] font-semibold px-1.5 py-0.5 rounded-md shrink-0", badge.color)}>
                  {badge.text}
                </span>
              )}
            </NavLink>
          </div>
        ))}
      </nav>

      {/* Schema settings + Language toggle */}
      <div className="p-3 border-t space-y-0.5">
        <button
          onClick={() => setShowSchemaSettings(true)}
          className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
        >
          <DatabaseZap className="w-4 h-4 shrink-0" />
          <span className="truncate">{dir === "rtl" ? "إعدادات المخطط" : "Schema"}</span>
          {source === "custom" && (
            <span className="ms-auto w-2 h-2 rounded-full bg-emerald-500 shrink-0" />
          )}
        </button>
        <button
          onClick={onToggleDir}
          className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
        >
          <Globe className="w-4 h-4 shrink-0" />
          {dir === "rtl" ? "English" : "العربية"}
        </button>
      </div>

      {showSchemaSettings && <SchemaSettings onClose={() => setShowSchemaSettings(false)} />}
    </aside>
  );
}
