import { cn } from "@/lib/utils";
import type { PipelineResult, ExtractedField } from "@/lib/api";
import { AlertTriangle, CheckCircle2 } from "lucide-react";

interface Props {
  result: PipelineResult;
  dir: "rtl" | "ltr";
}

export default function ResultViewer({ result, dir }: Props) {
  const pct = Math.round(result.confidence_avg * 100);

  return (
    <div className="flex gap-4 h-full animate-in fade-in slide-in-from-bottom-4 duration-500">
      {/* Left — document placeholder (real preview in Step 5) */}
      <div className="w-1/2 border rounded-xl bg-muted/30 flex items-center justify-center min-h-[480px]">
        <p className="text-sm text-muted-foreground">
          {dir === "rtl" ? "معاينة الوثيقة" : "Document Preview"}
        </p>
      </div>

      {/* Right — extracted fields */}
      <div className="w-1/2 flex flex-col gap-3 overflow-y-auto">
        {/* Summary bar */}
        <div className="flex items-center justify-between p-3 bg-muted rounded-lg">
          <div>
            <p className="text-xs text-muted-foreground uppercase tracking-wider">
              {dir === "rtl" ? "نوع الوثيقة" : "Doc Type"}
            </p>
            <p className="font-mono text-sm font-medium">{result.doc_type}</p>
          </div>
          <div className="text-center">
            <p className="text-xs text-muted-foreground uppercase tracking-wider">
              {dir === "rtl" ? "الثقة الكلية" : "Confidence"}
            </p>
            <p
              className={cn(
                "text-lg font-bold",
                pct >= 80 ? "text-green-600" : pct >= 60 ? "text-amber-500" : "text-destructive"
              )}
            >
              {pct}%
            </p>
          </div>
          <div className="text-end">
            <p className="text-xs text-muted-foreground uppercase tracking-wider">
              {dir === "rtl" ? "التركيبة" : "Combo"}
            </p>
            <p className="font-mono text-sm font-medium">{result.combo}</p>
          </div>
        </div>

        {/* Fields */}
        <div className="space-y-2">
          {result.fields.map((f: ExtractedField) => (
            <FieldRow key={f.field_id} field={f} dir={dir} />
          ))}
        </div>

        {/* Cost + latency footer */}
        <div className="mt-auto pt-2 border-t flex justify-between text-xs text-muted-foreground">
          <span>
            {dir === "rtl" ? "التكلفة التقديرية" : "Est. cost"}:{" "}
            ${result.estimated_cost_usd.toFixed(4)}
          </span>
          <span>
            {dir === "rtl" ? "الزمن الكلي" : "Total time"}:{" "}
            {(result.total_latency_ms / 1000).toFixed(2)}s
          </span>
        </div>
      </div>
    </div>
  );
}

function FieldRow({ field, dir }: { field: ExtractedField; dir: "rtl" | "ltr" }) {
  const pct = Math.round(field.confidence * 100);
  return (
    <div
      className={cn(
        "p-3 rounded-lg border text-sm transition-all",
        field.low_confidence
          ? "border-destructive/40 bg-destructive/5"
          : "border-border"
      )}
    >
      <div className="flex items-start justify-between gap-2 mb-1">
        <span className="font-mono text-xs text-muted-foreground">
          {field.field_id}
        </span>
        <div className="flex items-center gap-1 shrink-0">
          {field.low_confidence ? (
            <AlertTriangle className="w-3.5 h-3.5 text-destructive" />
          ) : (
            <CheckCircle2 className="w-3.5 h-3.5 text-green-500" />
          )}
          <span
            className={cn(
              "text-xs font-medium",
              field.low_confidence ? "text-destructive" : "text-green-600"
            )}
          >
            {pct}%
          </span>
        </div>
      </div>
      <p
        className={cn(
          "font-medium",
          dir === "rtl" ? "text-right" : "text-left",
          !field.value && "text-muted-foreground italic"
        )}
      >
        {field.value ?? (dir === "rtl" ? "— غير موجود" : "— not found")}
      </p>
    </div>
  );
}
