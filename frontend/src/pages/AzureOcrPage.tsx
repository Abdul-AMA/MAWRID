import { useState, useCallback } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { runAzureOcr, getAzureModels, AzureOcrResult } from "@/lib/api";
import {
  Upload, Loader2, FileText, RotateCcw, Copy, Check, Cloud, BookOpen,
} from "lucide-react";
import { cn } from "@/lib/utils";

type Phase = "idle" | "ready" | "running" | "done" | "error";

interface Props {
  dir: "rtl" | "ltr";
}

export default function AzureOcrPage({ dir }: Props) {
  const [file, setFile]         = useState<File | null>(null);
  const [fileUrl, setFileUrl]   = useState<string | null>(null);
  const [phase, setPhase]       = useState<Phase>("idle");
  const [dragging, setDragging] = useState(false);
  const [result, setResult]     = useState<AzureOcrResult | null>(null);
  const [model, setModel]       = useState("prebuilt-read");
  const [copied, setCopied]     = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const { data: modelsData } = useQuery({
    queryKey: ["azure-models"],
    queryFn: () => getAzureModels().then(r => r.data.models),
    staleTime: Infinity,
  });

  const models = modelsData ?? ["prebuilt-read", "prebuilt-layout"];

  const mutation = useMutation({
    mutationFn: (f: File) => runAzureOcr(f, model).then(r => r.data),
    onSuccess: data => { setResult(data); setPhase("done"); },
    onError: (err: unknown) => {
      const detail = (err as any)?.response?.data?.detail ?? String(err);
      setErrorMsg(String(detail));
      setPhase("error");
    },
  });

  const handleFile = useCallback((f: File) => {
    if (fileUrl) URL.revokeObjectURL(fileUrl);
    setFile(f);
    setFileUrl(URL.createObjectURL(f));
    setPhase("ready");
    setResult(null);
  }, [fileUrl]);

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault(); setDragging(false);
    const f = e.dataTransfer.files[0];
    if (f) handleFile(f);
  };

  const handleRun = () => {
    if (!file) return;
    setPhase("running");
    mutation.mutate(file);
  };

  const handleReset = () => {
    if (fileUrl) URL.revokeObjectURL(fileUrl);
    setFile(null); setFileUrl(null); setResult(null);
    setPhase("idle"); setCopied(false); setErrorMsg(null);
  };

  const handleCopy = () => {
    if (!result?.text) return;
    navigator.clipboard.writeText(result.text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const isRunning = phase === "running";
  const hasFile   = !!file;

  const modelDescriptions: Record<string, { en: string; ar: string }> = {
    "prebuilt-read":   { en: "Text extraction only", ar: "استخراج النص فقط" },
    "prebuilt-layout": { en: "Text + tables + structure", ar: "نص + جداول + هيكل" },
  };

  return (
    <div className="flex h-screen overflow-hidden">

      {/* ── Left: document preview ───────────────────────────────────────────── */}
      <div
        className="shrink-0 overflow-hidden border-r bg-muted/10 transition-[width,opacity] duration-700 ease-out"
        style={{ width: hasFile ? "50%" : "0%", opacity: hasFile ? 1 : 0 }}
      >
        {file && (
          <div className="flex flex-col h-full">
            <div className="h-12 px-4 border-b bg-white flex items-center gap-2 shrink-0">
              <FileText className="w-4 h-4 text-muted-foreground shrink-0" />
              <span className="text-sm font-medium truncate flex-1">{file.name}</span>
              {result && (
                <span className="text-xs text-muted-foreground shrink-0 font-mono">
                  {result.model} · {result.latency_ms} ms
                </span>
              )}
            </div>

            <div className="flex-1 overflow-y-auto bg-muted/20">
              {!result && phase !== "running" && fileUrl && (
                <div className="p-4 h-full">
                  {file.type === "application/pdf" ? (
                    <iframe src={fileUrl} className="w-full h-full min-h-[600px] border-none rounded-xl" title="Preview" />
                  ) : (
                    <img src={fileUrl} alt="Preview" className="max-w-full object-contain rounded-xl shadow mx-auto" />
                  )}
                </div>
              )}

              {phase === "running" && (
                <div className="flex flex-col items-center justify-center h-full gap-3 text-muted-foreground py-20">
                  <Loader2 className="w-8 h-8 animate-spin" />
                  <p className="text-sm">{dir === "rtl" ? "Azure يحلل الوثيقة..." : "Azure is analysing..."}</p>
                </div>
              )}

              {result && result.page_images.length > 0 && (
                <div className="p-4 space-y-4">
                  {result.page_images.map((img, pi) => (
                    <div key={pi} className="rounded-xl overflow-hidden shadow-sm border bg-white">
                      {result.page_images.length > 1 && (
                        <div className="px-3 py-1.5 text-xs text-muted-foreground border-b bg-muted/30 font-medium">
                          {dir === "rtl" ? `صفحة ${pi + 1}` : `Page ${pi + 1}`}
                        </div>
                      )}
                      <img src={`data:image/jpeg;base64,${img}`} alt={`Page ${pi + 1}`} className="w-full block" />
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* ── Right: upload / controls / result ───────────────────────────────── */}
      <div className="flex-1 min-w-0 flex flex-col overflow-hidden">

        {phase === "idle" && (
          <div className="flex-1 flex items-center justify-center p-8">
            <label
              className={cn(
                "flex flex-col items-center gap-6 p-16 border-2 border-dashed rounded-2xl cursor-pointer",
                "transition-all duration-300 max-w-sm w-full select-none",
                dragging
                  ? "border-sky-500 bg-sky-50 scale-[1.03] shadow-lg"
                  : "border-border hover:border-sky-400/60 hover:bg-muted/30 hover:shadow-sm"
              )}
              onDragOver={e => { e.preventDefault(); setDragging(true); }}
              onDragLeave={() => setDragging(false)}
              onDrop={handleDrop}
            >
              <div className={cn(
                "w-24 h-24 rounded-full flex items-center justify-center transition-all duration-300",
                dragging ? "bg-sky-100 scale-110" : "bg-muted"
              )}>
                <Upload className={cn("w-10 h-10 transition-colors", dragging ? "text-sky-500" : "text-muted-foreground")} />
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
                onChange={e => { const f = e.target.files?.[0]; if (f) handleFile(f); e.target.value = ""; }}
              />
            </label>
          </div>
        )}

        {phase !== "idle" && (
          <div className="flex-1 flex flex-col overflow-hidden">

            <div className="flex-1 overflow-y-auto p-6 space-y-3">
              <div className="flex items-center gap-2 mb-1">
                <Cloud className="w-4 h-4 text-sky-500" />
                <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
                  {dir === "rtl" ? "النص المستخرج" : "Extracted Text"}
                </h2>
                {result && (
                  <span className="ms-auto flex items-center gap-1 text-xs text-muted-foreground bg-muted px-2 py-0.5 rounded font-mono">
                    <BookOpen className="w-3 h-3" />
                    {result.pages_billed} {dir === "rtl" ? "صفحة" : "page(s)"}
                  </span>
                )}
              </div>

              {phase === "ready" && (
                <div className="flex items-center justify-center h-40 text-muted-foreground/60 text-sm">
                  {dir === "rtl" ? "اضغط «تشغيل» لبدء الاستخراج" : "Press Run to start extraction"}
                </div>
              )}

              {phase === "running" && (
                <div className="flex flex-col items-center justify-center h-40 gap-3 text-muted-foreground">
                  <Loader2 className="w-6 h-6 animate-spin" />
                  <p className="text-sm">{dir === "rtl" ? "Azure يقرأ الوثيقة..." : "Azure is reading the document..."}</p>
                </div>
              )}

              {phase === "error" && (
                <div className="p-4 rounded-xl bg-destructive/10 text-destructive text-sm space-y-1">
                  <p className="font-semibold">
                    {dir === "rtl" ? "فشل الاستخراج" : "Extraction failed"}
                  </p>
                  {errorMsg && (
                    <p className="font-mono text-xs break-all opacity-80">{errorMsg}</p>
                  )}
                </div>
              )}

              {phase === "done" && result && (
                <pre className="text-sm leading-relaxed whitespace-pre-wrap break-words font-mono bg-muted/30 rounded-xl p-4 border" dir="auto">
                  {result.text}
                </pre>
              )}
            </div>

            {/* Sticky bottom */}
            <div className="border-t bg-white px-6 py-5 space-y-3 shrink-0">

              <div className="space-y-1.5">
                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                  {dir === "rtl" ? "النموذج" : "Model"}
                </p>
                <div className="flex gap-2 flex-wrap">
                  {models.map(m => (
                    <button
                      key={m}
                      onClick={() => setModel(m)}
                      disabled={isRunning}
                      className={cn(
                        "flex flex-col px-3 py-2 rounded-lg border text-xs font-mono font-medium transition-all text-start",
                        model === m
                          ? "border-sky-500 bg-sky-50 text-sky-700 shadow-sm"
                          : "border-border text-muted-foreground hover:border-sky-300 hover:text-foreground"
                      )}
                    >
                      <span>{m}</span>
                      <span className={cn("text-[10px] font-normal mt-0.5", model === m ? "text-sky-500" : "text-muted-foreground/60")}>
                        {dir === "rtl"
                          ? modelDescriptions[m]?.ar
                          : modelDescriptions[m]?.en}
                      </span>
                    </button>
                  ))}
                </div>
              </div>

              <button
                onClick={handleRun}
                disabled={!file || isRunning || phase === "done"}
                className={cn(
                  "w-full flex items-center justify-center gap-2 py-3 rounded-xl font-semibold text-sm",
                  "bg-sky-600 text-white hover:bg-sky-700 transition-all duration-200",
                  "disabled:opacity-40 disabled:cursor-not-allowed shadow-sm hover:shadow"
                )}
              >
                {isRunning
                  ? <><Loader2 className="w-4 h-4 animate-spin" />{dir === "rtl" ? "جارٍ الاستخراج..." : "Running..."}</>
                  : phase === "done"
                  ? <><Check className="w-4 h-4" />{dir === "rtl" ? "اكتمل الاستخراج" : "Extraction complete"}</>
                  : <><Cloud className="w-4 h-4" />{dir === "rtl" ? "استخراج بـ Azure" : "Extract with Azure"}</>
                }
              </button>

              {phase === "done" && result?.text && (
                <button
                  onClick={handleCopy}
                  className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl border text-sm text-muted-foreground hover:text-foreground hover:border-sky-400/40 transition-colors"
                >
                  {copied
                    ? <><Check className="w-4 h-4 text-green-600" />{dir === "rtl" ? "تم النسخ" : "Copied!"}</>
                    : <><Copy className="w-4 h-4" />{dir === "rtl" ? "نسخ النص الكامل" : "Copy full text"}</>
                  }
                </button>
              )}

              {(phase === "done" || phase === "error") && (
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
    </div>
  );
}
