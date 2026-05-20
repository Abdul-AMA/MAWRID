import { cn } from "@/lib/utils";
import { CheckCircle2, Circle, Loader2, XCircle } from "lucide-react";
import type { StageResult } from "@/lib/api";

const STAGE_LABELS: Record<string, { ar: string; en: string }> = {
  ocr:        { ar: "التعرف الضوئي (OCR)",   en: "OCR" },
  classifier: { ar: "التصنيف",               en: "Classification" },
  extractor:  { ar: "استخراج الحقول",        en: "Extraction" },
  formfill:   { ar: "ملء النموذج",           en: "Form Fill" },
  validator:  { ar: "التحقق والثقة",         en: "Validation" },
};

const ALL_STAGES = ["ocr", "classifier", "extractor", "formfill", "validator"];

interface Props {
  stages: StageResult[];
  dir: "rtl" | "ltr";
}

export default function PipelineStatus({ stages, dir }: Props) {
  const stageMap = Object.fromEntries(stages.map((s) => [s.name, s]));

  return (
    <div className="space-y-1">
      {ALL_STAGES.map((name, i) => {
        const stage = stageMap[name];
        const status = stage?.status ?? "waiting";
        const label = STAGE_LABELS[name];

        return (
          <div
            key={name}
            className={cn(
              "flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-300",
              status === "done"    && "bg-green-50",
              status === "running" && "bg-primary/5 animate-pulse",
              status === "failed"  && "bg-destructive/5",
              status === "waiting" && "opacity-50"
            )}
          >
            <StageIcon status={status} />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium">
                {i + 1}. {dir === "rtl" ? label.ar : label.en}
              </p>
              {stage?.latency_ms != null && (
                <p className="text-xs text-muted-foreground">
                  {stage.latency_ms.toFixed(0)} ms
                </p>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function StageIcon({ status }: { status: string }) {
  if (status === "done")
    return <CheckCircle2 className="w-4 h-4 text-green-500 shrink-0" />;
  if (status === "running")
    return <Loader2 className="w-4 h-4 text-primary shrink-0 animate-spin" />;
  if (status === "failed")
    return <XCircle className="w-4 h-4 text-destructive shrink-0" />;
  return <Circle className="w-4 h-4 text-muted-foreground/40 shrink-0" />;
}
