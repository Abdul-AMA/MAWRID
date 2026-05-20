import { useState, useCallback } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  getTwoStageModels, runTwoStage,
  ThreeStageResult, ThreeStageStage1, ThreeStageStage2, ThreeStageStage3,
} from "@/lib/api";
import {
  Upload, Loader2, FileText, RotateCcw,
  Eye, Tag, AlignLeft, ArrowDown,
  Coins, Clock, ChevronDown, ChevronUp, CheckCircle2,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface Props { dir: "rtl" | "ltr" }
type RunPhase = "idle" | "ready" | "running" | "done" | "error";

const CONF_STYLE: Record<string, string> = {
  high:   "bg-emerald-100 text-emerald-700 border-emerald-200",
  medium: "bg-amber-100  text-amber-700  border-amber-200",
  low:    "bg-red-100    text-red-700    border-red-200",
};
const CONF_DOT: Record<string, string> = {
  high: "bg-emerald-500", medium: "bg-amber-400", low: "bg-red-400",
};

const GROQ_SCOUT = "groq/meta-llama/llama-4-scout-17b-16e-instruct";

// ── Small shared UI pieces ────────────────────────────────────────────────────

function Stat({ icon: Icon, value }: { icon: React.ElementType; value: string }) {
  return (
    <span className="flex items-center gap-1 text-xs text-muted-foreground font-mono bg-muted px-2 py-0.5 rounded">
      <Icon className="w-3 h-3" />{value}
    </span>
  );
}

function StageHeader({
  num, icon: Icon, color, title, subtitle, done, loading, tokens, ms,
}: {
  num: number; icon: React.ElementType; color: string; title: string; subtitle: string;
  done: boolean; loading: boolean; tokens?: number; ms?: number;
}) {
  return (
    <div className="flex items-center gap-3 px-5 py-3.5 border-b">
      <div className={cn("w-8 h-8 rounded-lg flex items-center justify-center shrink-0", color)}>
        <Icon className="w-4 h-4" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold">
          <span className="text-muted-foreground me-1.5">{num}.</span>{title}
        </p>
        <p className="text-xs text-muted-foreground">{subtitle}</p>
      </div>
      {tokens !== undefined && <Stat icon={Coins} value={String(tokens)} />}
      {ms !== undefined && ms > 0 && <Stat icon={Clock} value={`${Math.round(ms)} ms`} />}
      {loading && <Loader2 className="w-4 h-4 animate-spin text-muted-foreground shrink-0" />}
      {done && <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />}
    </div>
  );
}

function Connector({ active, label }: { active: boolean; label: string; dir?: "rtl" | "ltr" }) {
  return (
    <div className="flex flex-col items-center gap-0.5 py-0.5">
      <div className={cn("w-px h-4 transition-colors duration-500", active ? "bg-amber-300" : "bg-border")} />
      <div className={cn(
        "flex items-center gap-1.5 px-3 py-1 rounded-full border text-xs font-medium transition-all duration-500",
        active ? "border-amber-300 bg-amber-50 text-amber-700" : "border-border bg-muted/30 text-muted-foreground"
      )}>
        <AlignLeft className="w-3 h-3" />{label}
      </div>
      <div className={cn("w-px h-4 transition-colors duration-500", active ? "bg-amber-300" : "bg-border")} />
      <ArrowDown className={cn("w-4 h-4 transition-colors duration-500", active ? "text-amber-400" : "text-muted-foreground/30")} />
    </div>
  );
}

// ── Stage 1: OCR ──────────────────────────────────────────────────────────────

function Stage1Card({ data, loading, dir }: { data: ThreeStageStage1 | null; loading: boolean; dir: "rtl" | "ltr" }) {
  const [open, setOpen] = useState(false);
  const done = !!data && !loading;

  return (
    <div className={cn(
      "rounded-2xl border-2 bg-white transition-all duration-500",
      loading ? "border-indigo-400 shadow-md shadow-indigo-100 animate-pulse"
              : done ? "border-indigo-200" : "border-border",
    )}>
      <StageHeader
        num={1} icon={Eye} color={loading ? "bg-indigo-100" : "bg-indigo-50"}
        title={dir === "rtl" ? "استخراج النص (OCR)" : "OCR — Extract Text"}
        subtitle={dir === "rtl" ? "صورة → نص كامل فقط" : "image → raw text only"}
        done={done} loading={loading}
        tokens={data ? data.input_tokens + data.output_tokens : undefined}
        ms={data?.latency_ms}
      />
      <div className="p-5">
        {loading && <Spinner label={dir === "rtl" ? "النموذج يقرأ الصورة..." : "Reading image..."} color="text-indigo-400" />}
        {!loading && !data && <Empty label={dir === "rtl" ? "في انتظار التشغيل" : "Waiting to run"} />}
        {data && (
          <div className="border rounded-xl overflow-hidden">
            <button
              onClick={() => setOpen(v => !v)}
              className="w-full flex items-center gap-2 px-4 py-2.5 bg-muted/30 hover:bg-muted/60 transition-colors text-sm font-medium text-muted-foreground"
            >
              <AlignLeft className="w-4 h-4" />
              {dir === "rtl" ? "النص المستخرج" : "Extracted Text"}
              <span className="ms-auto text-xs opacity-60">{data.raw_text.length} {dir === "rtl" ? "حرف" : "chars"}</span>
              {open ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
            </button>
            {open && (
              <pre className="p-4 text-xs font-mono leading-relaxed whitespace-pre-wrap break-words bg-white max-h-52 overflow-y-auto" dir="auto">
                {data.raw_text}
              </pre>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Stage 2: Classification ───────────────────────────────────────────────────

function Stage2Card({ data, loading, dir }: { data: ThreeStageStage2 | null; loading: boolean; dir: "rtl" | "ltr" }) {
  const done = !!data && !loading;

  return (
    <div className={cn(
      "rounded-2xl border-2 bg-white transition-all duration-500",
      loading ? "border-amber-400 shadow-md shadow-amber-100 animate-pulse"
              : done ? "border-amber-200" : "border-border opacity-50",
    )}>
      <StageHeader
        num={2} icon={Tag} color={loading ? "bg-amber-100" : "bg-amber-50"}
        title={dir === "rtl" ? "تصنيف الوثيقة" : "Classify Document"}
        subtitle={dir === "rtl" ? "نص + 91 نوع → تحديد النوع" : "text + 91 types → document type"}
        done={done} loading={loading}
        tokens={data ? data.input_tokens + data.output_tokens : undefined}
        ms={data?.latency_ms}
      />
      <div className="p-5">
        {loading && <Spinner label={dir === "rtl" ? "تصنيف الوثيقة..." : "Classifying..."} color="text-amber-400" />}
        {!loading && !data && <Empty label={dir === "rtl" ? "في انتظار المرحلة الأولى" : "Waiting for Stage 1"} />}
        {data && (
          <div className="space-y-3">
            <div className="flex items-center gap-3 flex-wrap">
              <div className="flex-1 min-w-0">
                <p className="text-xs text-muted-foreground mb-1 font-medium uppercase tracking-wide">
                  {dir === "rtl" ? "نوع الوثيقة" : "Document Type"}
                </p>
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="px-3 py-1 rounded-lg bg-amber-50 border border-amber-200 text-amber-900 text-sm font-medium" dir="rtl">
                    {data.document_type_label || data.document_type}
                  </span>
                  <span className="text-xs text-muted-foreground font-mono">{data.document_type}</span>
                </div>
              </div>
              <div className="shrink-0 text-end">
                <p className="text-xs text-muted-foreground mb-1 font-medium uppercase tracking-wide">
                  {dir === "rtl" ? "الثقة" : "Confidence"}
                </p>
                <span className={cn("flex items-center gap-1.5 px-3 py-1 rounded-lg border text-sm font-medium", CONF_STYLE[data.confidence] ?? CONF_STYLE.low)}>
                  <span className={cn("w-1.5 h-1.5 rounded-full", CONF_DOT[data.confidence] ?? CONF_DOT.low)} />
                  {data.confidence}
                </span>
              </div>
            </div>
            <div className="text-xs text-muted-foreground bg-muted/40 rounded-lg px-3 py-2">
              {dir === "rtl"
                ? `سيتم استخراج ${data.field_count} حقل في المرحلة الثالثة`
                : `${data.field_count} fields will be extracted in Stage 3`}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Stage 3: Extraction ───────────────────────────────────────────────────────

function Stage3Card({ data, loading, dir }: { data: ThreeStageStage3 | null; loading: boolean; dir: "rtl" | "ltr" }) {
  const done = !!data && !loading;
  const entries = data ? Object.entries(data.fields) : [];
  const filled  = entries.filter(([, v]) => v !== null && v !== "").length;

  return (
    <div className={cn(
      "rounded-2xl border-2 bg-white transition-all duration-500",
      loading ? "border-emerald-400 shadow-md shadow-emerald-100 animate-pulse"
              : done ? "border-emerald-200" : "border-border opacity-50",
    )}>
      <StageHeader
        num={3} icon={AlignLeft} color={loading ? "bg-emerald-100" : "bg-emerald-50"}
        title={dir === "rtl" ? "استخراج الحقول" : "Extract Fields"}
        subtitle={dir === "rtl" ? "نص + تعريفات الحقول → JSON" : "text + field definitions → JSON"}
        done={done} loading={loading}
        tokens={data ? data.input_tokens + data.output_tokens : undefined}
        ms={data?.latency_ms}
      />
      <div className="p-5">
        {loading && <Spinner label={dir === "rtl" ? "استخراج البيانات..." : "Extracting fields..."} color="text-emerald-400" />}
        {!loading && !data && <Empty label={dir === "rtl" ? "في انتظار المرحلة الثانية" : "Waiting for Stage 2"} />}
        {data && entries.length === 0 && (
          <p className="text-sm text-muted-foreground text-center py-6">
            {dir === "rtl" ? "لم يتم استخراج أي حقول" : "No fields extracted"}
          </p>
        )}
        {data && entries.length > 0 && (
          <>
            <div className="flex items-center justify-between mb-3">
              <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide">
                {dir === "rtl" ? "النتائج" : "Results"}
              </p>
              <span className="text-xs font-mono text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded">
                {filled}/{entries.length} {dir === "rtl" ? "مُعبأ" : "filled"}
              </span>
            </div>
            <div className="space-y-1 max-h-72 overflow-y-auto">
              {entries.map(([id, value]) => {
                const empty = value === null || value === "";
                return (
                  <div key={id} className={cn("flex items-start gap-3 px-3 py-2 rounded-lg text-sm", empty ? "bg-muted/20" : "bg-emerald-50/60")}>
                    <span className="text-muted-foreground shrink-0 w-3 mt-0.5 text-xs">{empty ? "○" : "●"}</span>
                    <span className="text-muted-foreground text-xs flex-1 min-w-0" dir="rtl">{id}</span>
                    <span className={cn("text-xs font-mono min-w-0 max-w-[45%] text-end truncate", empty ? "text-muted-foreground/40 italic" : "text-foreground font-medium")} dir="auto">
                      {empty ? (dir === "rtl" ? "غير موجود" : "not found") : String(value)}
                    </span>
                  </div>
                );
              })}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

// ── Token summary ─────────────────────────────────────────────────────────────

function TokenSummary({ r, dir }: { r: ThreeStageResult; dir: "rtl" | "ltr" }) {
  const t1 = r.stage1.input_tokens + r.stage1.output_tokens;
  const t2 = r.stage2.input_tokens + r.stage2.output_tokens;
  const t3 = r.stage3.input_tokens + r.stage3.output_tokens;
  const ms  = r.stage1.latency_ms + r.stage2.latency_ms + r.stage3.latency_ms;
  return (
    <div className="rounded-xl border bg-muted/20 px-5 py-3 flex flex-wrap gap-5 text-xs">
      {[
        { label: dir === "rtl" ? "رموز ١ (صورة)" : "S1 tokens (image)", val: t1, color: "text-indigo-600" },
        { label: dir === "rtl" ? "رموز ٢ (تصنيف)" : "S2 tokens (classify)", val: t2, color: "text-amber-600" },
        { label: dir === "rtl" ? "رموز ٣ (استخراج)" : "S3 tokens (extract)", val: t3, color: "text-emerald-600" },
        { label: dir === "rtl" ? "المجموع" : "Total", val: t1 + t2 + t3, color: "font-bold" },
      ].map(({ label, val, color }) => (
        <div key={label}>
          <p className="text-muted-foreground mb-0.5">{label}</p>
          <p className={cn("font-mono font-semibold", color)}>{val}</p>
        </div>
      ))}
      <div className="ms-auto text-end">
        <p className="text-muted-foreground mb-0.5">{dir === "rtl" ? "الوقت الكلي" : "Total time"}</p>
        <p className="font-mono font-semibold">{Math.round(ms)} ms</p>
      </div>
    </div>
  );
}

// ── Tiny helpers ──────────────────────────────────────────────────────────────

function Spinner({ label, color }: { label: string; color: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-8 gap-3 text-muted-foreground">
      <Loader2 className={cn("w-6 h-6 animate-spin", color)} />
      <p className="text-sm">{label}</p>
    </div>
  );
}

function Empty({ label }: { label: string }) {
  return <div className="flex items-center justify-center py-8 text-muted-foreground/40 text-sm">{label}</div>;
}

function ModelChip({ backend }: { backend: string }) {
  const parts = backend.split("/");
  return <span className="font-mono text-xs text-muted-foreground">{parts[parts.length - 1].replace(/:.*$/, "")}</span>;
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function TwoStagePage({ dir }: Props) {
  const [file, setFile]       = useState<File | null>(null);
  const [fileUrl, setFileUrl] = useState<string | null>(null);
  const [phase, setPhase]     = useState<RunPhase>("idle");
  const [dragging, setDrag]   = useState(false);
  const [result, setResult]   = useState<ThreeStageResult | null>(null);
  const [errorMsg, setError]  = useState<string | null>(null);
  const [model, setModel]     = useState(GROQ_SCOUT);

  const { data: modelsData } = useQuery({
    queryKey: ["two-stage-models"],
    queryFn:  () => getTwoStageModels().then(r => r.data),
    staleTime: Infinity,
  });

  const allModels = [...new Set([
    ...(modelsData?.stage1 ?? []),
    ...(modelsData?.stage2 ?? []),
    ...(modelsData?.stage3 ?? []),
  ])];

  const mutation = useMutation({
    mutationFn: (f: File) => runTwoStage(f, model, model, model).then(r => r.data),
    onSuccess: data => { setResult(data); setPhase("done"); },
    onError: (err: unknown) => {
      setError(String((err as any)?.response?.data?.detail ?? err));
      setPhase("error");
    },
  });

  const handleFile = useCallback((f: File) => {
    if (fileUrl) URL.revokeObjectURL(fileUrl);
    setFile(f); setFileUrl(URL.createObjectURL(f));
    setPhase("ready"); setResult(null); setError(null);
  }, [fileUrl]);

  const handleRun = () => { if (!file) return; setPhase("running"); mutation.mutate(file); };
  const handleReset = () => {
    if (fileUrl) URL.revokeObjectURL(fileUrl);
    setFile(null); setFileUrl(null); setResult(null); setPhase("idle"); setError(null);
  };

  const isRunning = phase === "running";

  return (
    <div className="flex h-screen overflow-hidden">

      {/* ── Left: document preview ─────────────────────────────────────────── */}
      <div
        className="shrink-0 overflow-hidden border-r bg-muted/10 transition-[width,opacity] duration-700 ease-out"
        style={{ width: file ? "42%" : "0%", opacity: file ? 1 : 0 }}
      >
        {file && (
          <div className="flex flex-col h-full">
            <div className="h-12 px-4 border-b bg-white flex items-center gap-2 shrink-0">
              <FileText className="w-4 h-4 text-muted-foreground shrink-0" />
              <span className="text-sm font-medium truncate">{file.name}</span>
            </div>
            <div className="flex-1 overflow-y-auto p-4">
              {result?.stage1.page_images.length
                ? result.stage1.page_images.map((img, i) => (
                    <div key={i} className="rounded-xl overflow-hidden shadow-sm border bg-white mb-4">
                      {result.stage1.page_images.length > 1 && (
                        <div className="px-3 py-1.5 text-xs text-muted-foreground border-b bg-muted/30">
                          {dir === "rtl" ? `صفحة ${i + 1}` : `Page ${i + 1}`}
                        </div>
                      )}
                      <img src={`data:image/jpeg;base64,${img}`} alt="" className="w-full block" />
                    </div>
                  ))
                : fileUrl && (
                    file.type === "application/pdf"
                      ? <iframe src={fileUrl} className="w-full h-full min-h-96 border-none rounded-xl" title="Preview" />
                      : <img src={fileUrl} alt="Preview" className="max-w-full object-contain rounded-xl shadow mx-auto" />
                  )
              }
            </div>
          </div>
        )}
      </div>

      {/* ── Right: pipeline ────────────────────────────────────────────────── */}
      <div className="flex-1 min-w-0 flex flex-col overflow-hidden">

        {/* IDLE upload zone */}
        {phase === "idle" && (
          <div className="flex-1 flex items-center justify-center p-8">
            <label
              className={cn(
                "flex flex-col items-center gap-6 p-16 border-2 border-dashed rounded-2xl cursor-pointer",
                "transition-all duration-300 max-w-sm w-full select-none",
                dragging ? "border-primary bg-primary/5 scale-[1.03] shadow-lg"
                         : "border-border hover:border-primary/60 hover:bg-muted/30 hover:shadow-sm"
              )}
              onDragOver={e => { e.preventDefault(); setDrag(true); }}
              onDragLeave={() => setDrag(false)}
              onDrop={e => { e.preventDefault(); setDrag(false); const f = e.dataTransfer.files[0]; if (f) handleFile(f); }}
            >
              <div className={cn("w-24 h-24 rounded-full flex items-center justify-center transition-all", dragging ? "bg-primary/15 scale-110" : "bg-muted")}>
                <Upload className={cn("w-10 h-10", dragging ? "text-primary" : "text-muted-foreground")} />
              </div>
              <div className="text-center">
                <p className="font-semibold text-base">{dir === "rtl" ? "ارفع وثيقتك" : "Upload your document"}</p>
                <p className="text-sm text-muted-foreground mt-1.5">{dir === "rtl" ? "اسحب أو انقر" : "Drag & drop or click"}</p>
                <p className="text-xs text-muted-foreground/70 mt-1">PDF · PNG · JPG</p>
              </div>
              <input type="file" accept=".pdf,.png,.jpg,.jpeg,.tiff" className="hidden"
                onChange={e => { const f = e.target.files?.[0]; if (f) handleFile(f); e.target.value = ""; }} />
            </label>
          </div>
        )}

        {/* PIPELINE VIEW */}
        {phase !== "idle" && (
          <div className="flex-1 flex flex-col overflow-hidden">
            <div className="flex-1 overflow-y-auto p-6 space-y-1">

              {/* Title */}
              <div className="flex items-center gap-2 mb-4">
                <span className="w-2 h-2 rounded-full bg-indigo-400" />
                <span className="w-2 h-2 rounded-full bg-amber-400" />
                <span className="w-2 h-2 rounded-full bg-emerald-400" />
                <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider ms-1">
                  {dir === "rtl" ? "خط أنابيب ثلاثي المراحل" : "Three-Stage Pipeline"}
                </h2>
                {result && <span className="ms-auto"><ModelChip backend={model} /></span>}
              </div>

              {phase === "error" && (
                <div className="p-4 rounded-xl bg-destructive/10 text-destructive text-sm">
                  <p className="font-semibold mb-1">{dir === "rtl" ? "فشل التشغيل" : "Pipeline failed"}</p>
                  {errorMsg && <p className="font-mono text-xs break-all opacity-80">{errorMsg}</p>}
                </div>
              )}

              <Stage1Card data={result?.stage1 ?? null} loading={isRunning} dir={dir} />

              <Connector
                active={!!result?.stage1}
                label={dir === "rtl" ? "نص فقط ← بدون صورة" : "text only — no image"}
                dir={dir}
              />

              <Stage2Card data={result?.stage2 ?? null} loading={isRunning} dir={dir} />

              <Connector
                active={!!result?.stage2}
                label={dir === "rtl" ? "نص + نوع الوثيقة" : "text + document type"}
                dir={dir}
              />

              <Stage3Card data={result?.stage3 ?? null} loading={isRunning} dir={dir} />

              {result && <TokenSummary r={result} dir={dir} />}
            </div>

            {/* Bottom bar */}
            <div className="border-t bg-white px-6 py-4 space-y-3 shrink-0">
              <div className="space-y-1.5">
                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                  {dir === "rtl" ? "النموذج (للمراحل الثلاث)" : "Model (all 3 stages)"}
                </p>
                <div className="flex flex-col gap-1">
                  {allModels.map(m => (
                    <button key={m} onClick={() => setModel(m)} disabled={isRunning}
                      className={cn(
                        "px-3 py-1.5 rounded-lg border text-xs font-mono text-start transition-all truncate",
                        model === m
                          ? "border-primary/40 bg-primary/5 text-primary"
                          : "border-border text-muted-foreground hover:border-primary/30"
                      )}
                    >
                      {m.split("/").slice(1).join("/").replace(/:.*$/, "")}
                    </button>
                  ))}
                </div>
              </div>

              <button
                onClick={phase === "done" || phase === "error" ? handleReset : handleRun}
                disabled={!file || isRunning}
                className={cn(
                  "w-full flex items-center justify-center gap-2 py-3 rounded-xl font-semibold text-sm",
                  "transition-all duration-200 shadow-sm disabled:opacity-40 disabled:cursor-not-allowed",
                  phase === "done" || phase === "error"
                    ? "bg-muted text-muted-foreground hover:bg-muted/80"
                    : "bg-primary text-primary-foreground hover:bg-primary/90 hover:shadow"
                )}
              >
                {isRunning
                  ? <><Loader2 className="w-4 h-4 animate-spin" />{dir === "rtl" ? "جارٍ التشغيل..." : "Running..."}</>
                  : phase === "done" || phase === "error"
                  ? <><RotateCcw className="w-4 h-4" />{dir === "rtl" ? "وثيقة جديدة" : "New document"}</>
                  : <><Eye className="w-4 h-4" />{dir === "rtl" ? "تشغيل المراحل الثلاث" : "Run 3-Stage Pipeline"}</>
                }
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
