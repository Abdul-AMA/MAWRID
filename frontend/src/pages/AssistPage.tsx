import { useState, useCallback, useEffect, useMemo } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  runTwoStage, buildUICategories, saveDocument,
  UIField, UICategory,
} from "@/lib/api";
import {
  Upload, Loader2, FileText, RotateCcw,
  Save, CheckCircle2, Check, X, Sparkles,
  ChevronDown, ChevronUp, Cpu, Coins, Clock, Eye, Tag, AlignLeft,
  AlertCircle,
} from "lucide-react";
import { ThreeStageResult } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useSchemaCtx } from "@/lib/schemaContext";
import { useSchema } from "@/lib/useSchema";

interface Props {
  dir: "rtl" | "ltr"
  modelOverride?: string
  promptLang?: "ar" | "en" | "en-ocr"
}
type AIPhase = "idle" | "loading" | "filling" | "done";
type FieldAIState = "pending" | "accepted" | "ignored";

const GROQ_SCOUT = "groq/meta-llama/llama-4-scout-17b-16e-instruct";

// ── FieldInput ────────────────────────────────────────────────────────────────

function FieldInput({
  field, value, onChange, disabled, highlight,
}: {
  field: UIField; value: string; onChange: (v: string) => void;
  disabled?: boolean; highlight?: boolean;
}) {
  const base = cn(
    "w-full px-3 py-2 border rounded-lg text-sm bg-white",
    "focus:outline-none focus:ring-2 focus:ring-primary/30 transition-all",
    "disabled:opacity-50 disabled:cursor-not-allowed",
    highlight && "border-indigo-300 bg-indigo-50/40 ring-2 ring-indigo-100",
  );
  if (field.type === "lookup" && field.options?.length) {
    return (
      <select value={value} onChange={e => onChange(e.target.value)} disabled={disabled} className={cn(base, "cursor-pointer")}>
        <option value="">—</option>
        {field.options.map(opt => <option key={opt} value={opt}>{opt}</option>)}
      </select>
    );
  }
  if (field.type === "date")   return <input type="date"   value={value} onChange={e => onChange(e.target.value)} disabled={disabled} className={base} />;
  if (field.type === "number") return <input type="number" value={value} onChange={e => onChange(e.target.value)} disabled={disabled} className={base} />;
  return <input type="text" value={value} onChange={e => onChange(e.target.value)} disabled={disabled} className={base} />;
}

// ── PipelineDetails ───────────────────────────────────────────────────────────

const STAGE_META = [
  { key: "stage1", icon: Eye,      color: "text-indigo-500 bg-indigo-50 border-indigo-200", label: { en: "Stage 1 — OCR",      ar: "المرحلة ١ — استخراج النص" } },
  { key: "stage2", icon: Tag,      color: "text-amber-500 bg-amber-50 border-amber-200",    label: { en: "Stage 2 — Classify",  ar: "المرحلة ٢ — التصنيف" } },
  { key: "stage3", icon: AlignLeft, color: "text-emerald-500 bg-emerald-50 border-emerald-200", label: { en: "Stage 3 — Extract", ar: "المرحلة ٣ — الاستخراج" } },
] as const;

function PipelineDetails({ result, dir }: { result: ThreeStageResult; dir: "rtl" | "ltr" }) {
  const [open, setOpen] = useState<string | null>(null);

  const stages = [
    { ...STAGE_META[0], data: result.stage1 },
    { ...STAGE_META[1], data: result.stage2 },
    { ...STAGE_META[2], data: result.stage3 },
  ];

  const totalMs = Math.round(
    result.stage1.latency_ms + result.stage2.latency_ms + result.stage3.latency_ms
  );

  return (
    <div className="border-t pt-4 space-y-2">
      <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider px-1">
        {dir === "rtl" ? "تفاصيل خط الأنابيب" : "Pipeline Details"}
      </p>

      {stages.map(({ key, icon: Icon, color, label, data }) => {
        const isOpen  = open === key;
        const tokens  = data.input_tokens + data.output_tokens;
        const modelShort = data.model.split("/").slice(1).join("/").replace(/:.*$/, "") || data.model;

        return (
          <div key={key} className={cn("rounded-xl border overflow-hidden transition-all", isOpen ? "shadow-sm" : "")}>
            {/* Header row — always visible */}
            <button
              onClick={() => setOpen(isOpen ? null : key)}
              className="w-full flex items-center gap-3 px-3 py-2.5 bg-white hover:bg-muted/30 transition-colors text-start"
            >
              <span className={cn("w-6 h-6 rounded-md flex items-center justify-center shrink-0 border", color)}>
                <Icon className="w-3.5 h-3.5" />
              </span>
              <span className="text-xs font-semibold flex-1 truncate">
                {dir === "rtl" ? label.ar : label.en}
              </span>
              {/* Model chip */}
              <span className="flex items-center gap-1 text-[10px] font-mono text-muted-foreground bg-muted px-1.5 py-0.5 rounded shrink-0 max-w-[110px] truncate">
                <Cpu className="w-2.5 h-2.5 shrink-0" />
                {modelShort}
              </span>
              {/* Stats */}
              <span className="flex items-center gap-1 text-[10px] text-muted-foreground shrink-0">
                <Coins className="w-2.5 h-2.5" />{tokens}
              </span>
              <span className="flex items-center gap-1 text-[10px] text-muted-foreground shrink-0">
                <Clock className="w-2.5 h-2.5" />{Math.round(data.latency_ms)}ms
              </span>
              {isOpen
                ? <ChevronUp className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
                : <ChevronDown className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
              }
            </button>

            {/* Expanded: model + prompt + result */}
            {isOpen && (
              <div className="border-t bg-muted/20 px-3 py-3 space-y-3">
                {/* Full model */}
                <div className="space-y-1">
                  <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide">
                    {dir === "rtl" ? "النموذج" : "Model"}
                  </p>
                  <p className="text-xs font-mono text-foreground break-all">{data.model}</p>
                </div>

                {/* Prompt */}
                {data.prompt && (
                  <div className="space-y-1">
                    <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide">
                      {dir === "rtl" ? "البرومبت المرسل" : "Prompt Sent"}
                    </p>
                    <pre className="text-[11px] leading-relaxed whitespace-pre-wrap break-words font-mono bg-white border rounded-lg p-3 max-h-48 overflow-y-auto" dir="rtl">
                      {data.prompt}
                    </pre>
                  </div>
                )}

                {/* Result */}
                <div className="space-y-1">
                  <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide">
                    {dir === "rtl" ? "النتيجة" : "Result"}
                  </p>

                  {key === "stage1" && (
                    <pre className="text-[11px] leading-relaxed whitespace-pre-wrap break-words font-mono bg-white border rounded-lg p-3 max-h-48 overflow-y-auto" dir="rtl">
                      {result.stage1.raw_text || (dir === "rtl" ? "— لا نص —" : "— no text —")}
                    </pre>
                  )}

                  {key === "stage2" && (
                    <div className="bg-white border rounded-lg p-3 space-y-2 text-xs font-mono">
                      <div className="flex items-center justify-between">
                        <span className="text-muted-foreground">{dir === "rtl" ? "نوع الوثيقة" : "document_type"}</span>
                        <span className="font-semibold text-amber-700" dir="rtl">{result.stage2.document_type}</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-muted-foreground">{dir === "rtl" ? "التسمية" : "label"}</span>
                        <span className="font-semibold" dir="rtl">{result.stage2.document_type_label}</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-muted-foreground">{dir === "rtl" ? "الثقة" : "confidence"}</span>
                        <span className={cn(
                          "font-semibold px-1.5 py-0.5 rounded",
                          result.stage2.confidence === "high"   ? "bg-emerald-100 text-emerald-700" :
                          result.stage2.confidence === "medium" ? "bg-amber-100 text-amber-700" :
                                                                   "bg-red-100 text-red-700"
                        )}>
                          {result.stage2.confidence}
                        </span>
                      </div>
                    </div>
                  )}

                  {key === "stage3" && (
                    <div className="bg-white border rounded-lg overflow-hidden">
                      {Object.entries(result.stage3.fields).length === 0 ? (
                        <p className="text-xs text-muted-foreground p-3">
                          {dir === "rtl" ? "— لم يتم استخراج حقول —" : "— no fields extracted —"}
                        </p>
                      ) : (
                        <div className="divide-y max-h-48 overflow-y-auto">
                          {Object.entries(result.stage3.fields).map(([id, val]) => (
                            <div key={id} className="flex items-start gap-2 px-3 py-1.5 text-xs">
                              <span className="text-muted-foreground font-mono shrink-0 w-36 truncate">{id}</span>
                              <span className={cn(
                                "font-medium break-all min-w-0",
                                val === null || val === "" ? "text-muted-foreground/40 italic" : "text-foreground"
                              )} dir="auto">
                                {val === null || val === "" ? "null" : String(val)}
                              </span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        );
      })}

      {/* Total time footer */}
      <div className="flex items-center justify-between px-3 py-2 rounded-xl bg-muted/40 border mt-1">
        <span className="text-xs font-semibold text-muted-foreground">
          {dir === "rtl" ? "الوقت الكلي" : "Total time"}
        </span>
        <span className="flex items-center gap-1.5 text-sm font-bold tabular-nums text-foreground">
          <Clock className="w-3.5 h-3.5 text-muted-foreground" />
          {totalMs >= 1000
            ? `${(totalMs / 1000).toFixed(2)}s`
            : `${totalMs}ms`}
        </span>
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function AssistPage({ dir, modelOverride, promptLang = "ar" }: Props) {
  const [file, setFile]       = useState<File | null>(null);
  const [fileUrl, setFileUrl] = useState<string | null>(null);
  const [ready, setReady]     = useState(false);
  const [dragging, setDrag]   = useState(false);
  const [category, setCategory] = useState("");
  const [docType, setDocType]   = useState("");
  const [fieldValues, setFieldValues] = useState<Record<string, string>>({});
  const [saved, setSaved] = useState(false);

  // AI fill
  const [aiPhase, setAiPhase]             = useState<AIPhase>("idle");
  const [aiValues, setAiValues]           = useState<Record<string, string>>({});
  const [fieldAIStates, setFieldAIStates] = useState<Record<string, FieldAIState>>({});
  const [fillStep, setFillStep]           = useState(0);
  const [fillProgress, setFillProgress]   = useState(0);
  const [lastResult, setLastResult]       = useState<ThreeStageResult | null>(null);
  const [errorMsg, setErrorMsg]           = useState<string | null>(null);
  const model = modelOverride ?? GROQ_SCOUT;

  const qc = useQueryClient();
  const { customToken } = useSchemaCtx();
  const { data: schemaData } = useSchema();

  const categories: UICategory[] = useMemo(
    () => schemaData ? buildUICategories(schemaData) : [],
    [schemaData],
  );

  const selectedCat  = categories.find(c => c.id === category);
  const selectedType = selectedCat?.types.find(t => t.id === docType);
  const docFields    = useMemo(() => selectedType?.fields ?? [], [selectedType]);

  // Fields that AI produced values for, in docFields order
  const fieldsToFill = useMemo(
    () => docFields.filter(f => aiValues[f.id] !== undefined && aiValues[f.id] !== ""),
    [docFields, aiValues],
  );

  // Sequential fill animation
  useEffect(() => {
    if (aiPhase !== "filling") return;
    if (fillStep >= fieldsToFill.length) {
      setAiPhase("done");
      setFillProgress(100);
      return;
    }
    const timer = setTimeout(() => {
      const field = fieldsToFill[fillStep];
      setFieldAIStates(prev => ({ ...prev, [field.id]: "pending" }));
      setFieldValues(prev => ({ ...prev, [field.id]: aiValues[field.id] }));
      const next = fillStep + 1;
      setFillStep(next);
      setFillProgress(Math.round(next / Math.max(fieldsToFill.length, 1) * 100));
    }, 220);
    return () => clearTimeout(timer);
  }, [aiPhase, fillStep, fieldsToFill, aiValues]);

  // AI mutation
  const aiMutation = useMutation({
    mutationFn: (f: File) => runTwoStage(f, model, model, model, promptLang, customToken || undefined).then(r => r.data),
    onSuccess: data => {
      setLastResult(data);
      // Auto-detect category + docType from stage 2
      const detectedType = data.stage2.document_type;
      const catId = schemaData?.documents[detectedType]?.category ?? "";
      setCategory(catId);
      setDocType(detectedType);
      setFieldValues({});

      const vals: Record<string, string> = {};
      Object.entries(data.stage3.fields).forEach(([k, v]) => {
        if (v !== null && v !== undefined && String(v).trim() !== "") vals[k] = String(v);
      });
      setAiValues(vals);
      setFieldAIStates({});
      setFillStep(0);
      setFillProgress(0);
      setAiPhase("filling");
    },
    onError: (err: unknown) => {
      setAiPhase("idle");
      const raw = err instanceof Error ? err.message : String(err);
      const detail = (() => {
        try { return (JSON.parse(raw) as { detail?: string }).detail ?? raw; } catch { return raw; }
      })();
      if (detail.includes("rate_limit") || detail.includes("Rate limit") || detail.includes("429")) {
        const wait = detail.match(/try again in (.+?)\./i)?.[1];
        setErrorMsg(`Groq rate limit reached.${wait ? ` Try again in ${wait}.` : " Try again soon."}`);
      } else {
        setErrorMsg(detail.length > 200 ? detail.slice(0, 200) + "…" : detail);
      }
    },
  });

  // Save mutation
  const saveMutation = useMutation({
    mutationFn: () => saveDocument({
      file:          file!,
      category:      selectedCat?.id ?? "",
      categoryLabel: selectedCat?.labelAr ?? "",
      docType,
      docTypeLabel:  selectedType?.labelAr ?? docType,
      combo:         model.split("/").pop()?.replace(/:.*$/, "") ?? model,
      confidence:    0,
      cost:          0,
      latency:       0,
      fields: docFields.map(fd => ({
        field_id:   fd.id,
        label_ar:   fd.labelAr,
        value:      fieldValues[fd.id] ?? null,
        confidence: 0,
      })),
    }),
    onSuccess: () => {
      setSaved(true);
      qc.invalidateQueries({ queryKey: ["saved-documents"] });
    },
  });

  const resetAI = () => {
    setAiPhase("idle"); setAiValues({}); setFieldAIStates({});
    setFillStep(0); setFillProgress(0); setLastResult(null);
  };

  const handleFile = useCallback((f: File) => {
    if (fileUrl) URL.revokeObjectURL(fileUrl);
    setFile(f); setFileUrl(URL.createObjectURL(f));
    setReady(true);
    setCategory(""); setDocType(""); setFieldValues({}); setSaved(false);
    resetAI();
  }, [fileUrl]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleFillWithAI = () => {
    if (!file) return;
    setAiPhase("loading");
    setAiValues({}); setFieldAIStates({});
    setFillStep(0); setFillProgress(0);
    setErrorMsg(null);
    aiMutation.mutate(file);
  };

  const acceptField = (id: string) => setFieldAIStates(prev => ({ ...prev, [id]: "accepted" }));
  const ignoreField = (id: string) => {
    setFieldAIStates(prev => ({ ...prev, [id]: "ignored" }));
    setFieldValues(prev => ({ ...prev, [id]: "" }));
  };

  const handleReset = () => {
    if (fileUrl) URL.revokeObjectURL(fileUrl);
    setFile(null); setFileUrl(null); setReady(false);
    setCategory(""); setDocType(""); setFieldValues({}); setSaved(false);
    resetAI();
  };

  const isAIActive   = aiPhase === "loading" || aiPhase === "filling";
  const canFillAI    = !!file && !isAIActive;
  const canSave      = !!file && !!category && !!docType && !isAIActive && !saved;
  const pendingCount = Object.values(fieldAIStates).filter(s => s === "pending").length;

  const isClaude = model.startsWith("claude/");
  const providerLabel = isClaude ? "Claude" : "Groq";
  const providerStyle = isClaude
    ? "bg-violet-50 text-violet-700 border-violet-200"
    : "bg-orange-50 text-orange-700 border-orange-200";

  return (
    <div className="flex h-screen overflow-hidden relative">

      {/* ── Left: document preview ─────────────────────────────────────────── */}
      <div
        className="shrink-0 overflow-hidden border-r bg-muted/10 transition-[width,opacity] duration-700 ease-out"
        style={{ width: file ? "50%" : "0%", opacity: file ? 1 : 0 }}
      >
        {file && fileUrl && (
          <div className="flex flex-col h-full">
            <div className="h-12 px-4 border-b bg-white flex items-center gap-2 shrink-0">
              <FileText className="w-4 h-4 text-muted-foreground shrink-0" />
              <span className="text-sm font-medium truncate flex-1">{file.name}</span>
              <span className="text-xs text-muted-foreground shrink-0">
                {(file.size / 1024).toFixed(0)} KB
              </span>
              <span className={cn("text-[10px] font-bold px-2 py-0.5 rounded-full border shrink-0", providerStyle)}>
                {providerLabel}
              </span>
            </div>
            <div className="flex-1 overflow-hidden">
              {file.type === "application/pdf"
                ? <iframe src={fileUrl} className="w-full h-full border-none" title="Document preview" />
                : (
                  <div className="h-full flex items-center justify-center p-6 bg-muted/20">
                    <img src={fileUrl} alt="Document preview"
                      className="max-h-full max-w-full object-contain rounded-xl shadow" />
                  </div>
                )
              }
            </div>
          </div>
        )}
      </div>

      {/* ── Right ──────────────────────────────────────────────────────────── */}
      <div className="flex-1 min-w-0 flex flex-col overflow-hidden">

        {/* IDLE: upload zone */}
        {!ready && (
          <div className="flex-1 flex items-center justify-center p-8">
            <label
              className={cn(
                "flex flex-col items-center gap-6 p-16 border-2 border-dashed rounded-2xl cursor-pointer",
                "transition-all duration-300 max-w-sm w-full select-none",
                dragging
                  ? "border-primary bg-primary/5 scale-[1.03] shadow-lg"
                  : "border-border hover:border-primary/60 hover:bg-muted/30 hover:shadow-sm"
              )}
              onDragOver={e => { e.preventDefault(); setDrag(true); }}
              onDragLeave={() => setDrag(false)}
              onDrop={e => { e.preventDefault(); setDrag(false); const f = e.dataTransfer.files[0]; if (f) handleFile(f); }}
            >
              <div className={cn(
                "w-24 h-24 rounded-full flex items-center justify-center transition-all",
                dragging ? "bg-primary/15 scale-110" : "bg-muted"
              )}>
                <Upload className={cn("w-10 h-10", dragging ? "text-primary" : "text-muted-foreground")} />
              </div>
              <div className="text-center">
                <p className="font-semibold text-base">
                  {dir === "rtl" ? "ارفع وثيقتك" : "Upload your document"}
                </p>
                <p className="text-sm text-muted-foreground mt-1.5">
                  {dir === "rtl" ? "اسحب الملف هنا أو انقر للاختيار" : "Drag & drop or click to select"}
                </p>
                <p className="text-xs text-muted-foreground/70 mt-1">PDF · PNG · JPG · TIFF</p>
              </div>
              <input type="file" accept=".pdf,.png,.jpg,.jpeg,.tiff" className="hidden"
                onChange={e => { const f = e.target.files?.[0]; if (f) handleFile(f); e.target.value = ""; }} />
            </label>
          </div>
        )}

        {/* READY: form + bottom bar */}
        {ready && (
          <div className="flex-1 flex flex-col overflow-hidden">

            {/* Scrollable: dropdowns + fields */}
            <div className="flex-1 overflow-y-auto p-6 space-y-5">

              {/* Category */}
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                  {dir === "rtl" ? "الفئة" : "Category"}
                </label>
                <select
                  value={category}
                  onChange={e => {
                    setCategory(e.target.value);
                    setDocType(""); setFieldValues({}); setSaved(false); resetAI();
                  }}
                  disabled={isAIActive}
                  className="w-full px-3 py-2.5 border rounded-xl text-sm bg-white focus:outline-none focus:ring-2 focus:ring-primary/30 disabled:opacity-50 cursor-pointer"
                >
                  <option value="">{dir === "rtl" ? "اختر الفئة..." : "Select category..."}</option>
                  {categories.map(c => <option key={c.id} value={c.id}>{c.labelAr}</option>)}
                </select>
              </div>

              {/* Doc type */}
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                  {dir === "rtl" ? "نوع الوثيقة" : "Document Type"}
                </label>
                <select
                  value={docType}
                  onChange={e => {
                    setDocType(e.target.value);
                    setFieldValues({}); setSaved(false); resetAI();
                  }}
                  disabled={!category || isAIActive}
                  className="w-full px-3 py-2.5 border rounded-xl text-sm bg-white focus:outline-none focus:ring-2 focus:ring-primary/30 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
                >
                  <option value="">{dir === "rtl" ? "اختر نوع الوثيقة..." : "Select document type..."}</option>
                  {selectedCat?.types.map(t => <option key={t.id} value={t.id}>{t.labelAr}</option>)}
                </select>
              </div>

              {/* Fields */}
              {docFields.length > 0 && (
                <div className="animate-in fade-in slide-in-from-bottom-2 duration-400">
                  <div className="border-t pt-5">
                    <div className="flex items-center justify-between mb-4">
                      <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                        {dir === "rtl" ? "الحقول" : "Fields"}
                        <span className="ms-2 font-normal normal-case text-muted-foreground/60">
                          {docFields.length} {dir === "rtl" ? "حقل" : "fields"}
                        </span>
                      </p>
                      {pendingCount > 0 && (
                        <span className="text-xs font-medium text-indigo-600 bg-indigo-50 border border-indigo-200 px-2.5 py-0.5 rounded-full">
                          {pendingCount} {dir === "rtl" ? "في انتظار المراجعة" : "pending review"}
                        </span>
                      )}
                    </div>

                    <div className="space-y-2">
                      {docFields.map(field => {
                        const aiState  = fieldAIStates[field.id];
                        const isPending = aiState === "pending";

                        return (
                          <div
                            key={field.id}
                            className={cn(
                              "rounded-xl px-3 pt-2.5 pb-3 -mx-3 transition-colors duration-300",
                              isPending ? "bg-indigo-50/60" : "bg-transparent",
                            )}
                          >
                            {/* Label row */}
                            <div className="flex items-center justify-between gap-2 mb-1.5">
                              <label className="text-xs font-medium text-muted-foreground leading-none">
                                {field.labelAr}
                                {field.required && <span className="text-destructive ms-0.5">*</span>}
                                <span className="ms-1.5 text-muted-foreground/50 font-normal">({field.type})</span>
                              </label>

                              {/* AI state badge / action buttons */}
                              <div className="flex items-center gap-1.5 shrink-0">
                                {isPending && (
                                  <>
                                    <span className="text-[10px] font-bold text-indigo-500 bg-indigo-100 border border-indigo-200 px-1.5 py-0.5 rounded tracking-wide">
                                      AI
                                    </span>
                                    <button
                                      onClick={() => acceptField(field.id)}
                                      className="flex items-center gap-1 px-2 py-0.5 rounded-md bg-emerald-50 border border-emerald-200 text-emerald-700 text-xs font-medium hover:bg-emerald-100 transition-colors"
                                    >
                                      <Check className="w-3 h-3" />
                                      {dir === "rtl" ? "قبول" : "Accept"}
                                    </button>
                                    <button
                                      onClick={() => ignoreField(field.id)}
                                      className="flex items-center gap-1 px-2 py-0.5 rounded-md bg-red-50 border border-red-200 text-red-600 text-xs font-medium hover:bg-red-100 transition-colors"
                                    >
                                      <X className="w-3 h-3" />
                                      {dir === "rtl" ? "تجاهل" : "Ignore"}
                                    </button>
                                  </>
                                )}
                                {aiState === "accepted" && (
                                  <span className="text-xs text-emerald-600 flex items-center gap-1 font-medium">
                                    <Check className="w-3 h-3" />
                                    {dir === "rtl" ? "مقبول" : "Accepted"}
                                  </span>
                                )}
                                {aiState === "ignored" && (
                                  <span className="text-xs text-muted-foreground/40 flex items-center gap-1">
                                    <X className="w-3 h-3" />
                                    {dir === "rtl" ? "متجاهل" : "Ignored"}
                                  </span>
                                )}
                              </div>
                            </div>

                            <FieldInput
                              field={field}
                              value={fieldValues[field.id] ?? ""}
                              onChange={v => setFieldValues(prev => ({ ...prev, [field.id]: v }))}
                              disabled={isAIActive}
                              highlight={isPending}
                            />
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </div>
              )}

              {/* ── Pipeline details (shown after AI run) ───────────────── */}
              {lastResult && aiPhase !== "loading" && (
                <PipelineDetails result={lastResult} dir={dir} />
              )}
            </div>

            {/* ── Bottom bar ───────────────────────────────────────────────── */}
            <div className="border-t bg-white px-6 py-5 space-y-4 shrink-0">

              {/* Progress bar */}
              {aiPhase !== "idle" && (
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between text-xs text-muted-foreground">
                    <span>
                      {aiPhase === "loading"
                        ? (dir === "rtl" ? "الذكاء الاصطناعي يقرأ الوثيقة..." : "AI reading document...")
                        : aiPhase === "filling"
                        ? (dir === "rtl"
                            ? `جارٍ ملء الحقول... (${fillStep}/${fieldsToFill.length})`
                            : `Filling fields... (${fillStep}/${fieldsToFill.length})`)
                        : (dir === "rtl"
                            ? `اكتمل — ${fieldsToFill.length} حقل`
                            : `Done — ${fieldsToFill.length} fields filled`)
                      }
                    </span>
                    {aiPhase !== "loading" && (
                      <span className="font-mono tabular-nums">{fillProgress}%</span>
                    )}
                  </div>
                  <div className="h-1.5 rounded-full bg-muted overflow-hidden">
                    {aiPhase === "loading" ? (
                      <div className="h-full w-1/2 rounded-full bg-indigo-300 animate-pulse" />
                    ) : (
                      <div
                        className={cn(
                          "h-full rounded-full transition-all duration-300",
                          aiPhase === "done" ? "bg-emerald-500" : "bg-indigo-500",
                        )}
                        style={{ width: `${fillProgress}%` }}
                      />
                    )}
                  </div>
                </div>
              )}

              {/* Fill with AI button */}
              <button
                onClick={handleFillWithAI}
                disabled={!canFillAI}
                className={cn(
                  "w-full flex items-center justify-center gap-2 py-3 rounded-xl font-semibold text-sm",
                  "transition-all duration-200 shadow-sm disabled:opacity-40 disabled:cursor-not-allowed",
                  isAIActive
                    ? "bg-indigo-50 text-indigo-500 border border-indigo-200 cursor-not-allowed"
                    : aiPhase === "done"
                    ? "bg-muted text-muted-foreground hover:bg-muted/80"
                    : "bg-indigo-600 text-white hover:bg-indigo-700 hover:shadow",
                )}
              >
                {isAIActive
                  ? <><Loader2 className="w-4 h-4 animate-spin" />{dir === "rtl" ? "جارٍ الملء..." : "Filling..."}</>
                  : aiPhase === "done"
                  ? <><Sparkles className="w-4 h-4" />{dir === "rtl" ? "ملء مجدداً بالذكاء الاصطناعي" : "Fill Again with AI"}</>
                  : <><Sparkles className="w-4 h-4" />{dir === "rtl" ? "ملء بالذكاء الاصطناعي" : "Fill with AI"}</>
                }
              </button>

              {/* Save */}
              {!saved ? (
                <button
                  onClick={() => saveMutation.mutate()}
                  disabled={!canSave || saveMutation.isPending}
                  className={cn(
                    "w-full flex items-center justify-center gap-2 py-3 rounded-xl font-semibold text-sm",
                    "bg-emerald-600 text-white hover:bg-emerald-700 transition-all duration-200",
                    "disabled:opacity-40 disabled:cursor-not-allowed shadow-sm hover:shadow",
                  )}
                >
                  {saveMutation.isPending
                    ? <><Loader2 className="w-4 h-4 animate-spin" />{dir === "rtl" ? "جارٍ الحفظ..." : "Saving..."}</>
                    : <><Save className="w-4 h-4" />{dir === "rtl" ? "حفظ السجل" : "Save Record"}</>
                  }
                </button>
              ) : (
                <div className="flex items-center justify-center gap-2 py-3 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-700 text-sm font-medium animate-in fade-in duration-300">
                  <CheckCircle2 className="w-4 h-4" />
                  {dir === "rtl" ? "تم الحفظ بنجاح" : "Saved successfully"}
                </div>
              )}

              {/* Reset */}
              {saved && (
                <button
                  onClick={handleReset}
                  className="w-full flex items-center justify-center gap-2 py-2 text-xs text-muted-foreground hover:text-foreground transition-colors"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                  {dir === "rtl" ? "رفع وثيقة أخرى" : "Upload another document"}
                </button>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Error toast */}
      {errorMsg && (
        <div className="absolute bottom-6 left-1/2 -translate-x-1/2 z-50 animate-in slide-in-from-bottom-3 fade-in duration-300">
          <div className="flex items-start gap-3 bg-red-600 text-white text-sm font-medium px-4 py-3 rounded-xl shadow-xl max-w-sm">
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
            <span className="flex-1">{errorMsg}</span>
            <button onClick={() => setErrorMsg(null)} className="shrink-0 opacity-70 hover:opacity-100 transition-opacity">
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
