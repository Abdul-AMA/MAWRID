import { useQuery } from "@tanstack/react-query";
import { getExperiments, ExperimentRun } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useState } from "react";
import { ArrowUpDown } from "lucide-react";

type SortKey = keyof Pick<
  ExperimentRun,
  "combo" | "doc_type" | "precision" | "confidence_avg" | "estimated_cost_usd" | "latency_ms" | "timestamp"
>;

interface Props {
  dir: "rtl" | "ltr";
}

const COLS: { key: SortKey; ar: string; en: string }[] = [
  { key: "timestamp",          ar: "الوقت",         en: "Time" },
  { key: "combo",              ar: "التركيبة",      en: "Combo" },
  { key: "doc_type",           ar: "نوع الوثيقة",   en: "Doc Type" },
  { key: "precision",          ar: "الدقة",         en: "Precision" },
  { key: "confidence_avg",     ar: "الثقة",         en: "Confidence" },
  { key: "estimated_cost_usd", ar: "التكلفة",       en: "Cost (USD)" },
  { key: "latency_ms",         ar: "الزمن (ms)",    en: "Latency (ms)" },
];

export default function ExperimentLog({ dir }: Props) {
  const { data, isLoading } = useQuery({
    queryKey: ["experiments"],
    queryFn: () => getExperiments().then((r) => r.data),
    refetchInterval: 10_000,
  });

  const [sortKey, setSortKey] = useState<SortKey>("timestamp");
  const [sortAsc, setSortAsc] = useState(false);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-32 text-muted-foreground text-sm">
        {dir === "rtl" ? "جارٍ التحميل..." : "Loading..."}
      </div>
    );
  }

  const runs = [...(data?.runs ?? [])].sort((a, b) => {
    const va = a[sortKey] ?? "";
    const vb = b[sortKey] ?? "";
    if (va < vb) return sortAsc ? -1 : 1;
    if (va > vb) return sortAsc ? 1 : -1;
    return 0;
  });

  const handleSort = (key: SortKey) => {
    if (key === sortKey) setSortAsc((p) => !p);
    else { setSortKey(key); setSortAsc(true); }
  };

  return (
    <div className="overflow-x-auto rounded-xl border">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b bg-muted/50">
            {COLS.map((col) => (
              <th
                key={col.key}
                onClick={() => handleSort(col.key)}
                className="px-4 py-3 text-start font-medium text-muted-foreground cursor-pointer hover:text-foreground whitespace-nowrap select-none"
              >
                <div className="flex items-center gap-1">
                  {dir === "rtl" ? col.ar : col.en}
                  <ArrowUpDown className="w-3 h-3 opacity-50" />
                </div>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {runs.length === 0 && (
            <tr>
              <td
                colSpan={COLS.length}
                className="px-4 py-8 text-center text-muted-foreground"
              >
                {dir === "rtl" ? "لا توجد تجارب بعد" : "No experiments yet"}
              </td>
            </tr>
          )}
          {runs.map((run, i) => (
            <tr
              key={run.run_id}
              className={cn(
                "border-b last:border-0 hover:bg-muted/30 transition-colors",
                i % 2 === 0 ? "bg-white" : "bg-muted/10"
              )}
            >
              <td className="px-4 py-3 text-muted-foreground text-xs">
                {new Date(run.timestamp).toLocaleString(
                  dir === "rtl" ? "ar-PS" : "en-US",
                  { dateStyle: "short", timeStyle: "short" }
                )}
              </td>
              <td className="px-4 py-3 font-mono font-semibold text-xs">
                {run.combo}
              </td>
              <td className="px-4 py-3 text-xs">{run.doc_type}</td>
              <td className="px-4 py-3">
                <ConfBadge value={run.precision} />
              </td>
              <td className="px-4 py-3">
                <ConfBadge value={run.confidence_avg} />
              </td>
              <td className="px-4 py-3 font-mono text-xs">
                ${run.estimated_cost_usd.toFixed(4)}
              </td>
              <td className="px-4 py-3 font-mono text-xs">
                {run.latency_ms.toFixed(0)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ConfBadge({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  return (
    <span
      className={cn(
        "inline-block px-2 py-0.5 rounded text-xs font-medium",
        pct >= 80 ? "bg-green-100 text-green-700" :
        pct >= 60 ? "bg-amber-100 text-amber-700" :
                    "bg-red-100 text-red-700"
      )}
    >
      {pct}%
    </span>
  );
}
