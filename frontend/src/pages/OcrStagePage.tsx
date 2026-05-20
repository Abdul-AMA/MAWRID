import { useState, useCallback, useRef, useEffect } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { runOcr, getOcrConfig, OcrResult, OcrPage, LocalOcrBackend, LOCAL_OCR_BACKENDS } from "@/lib/api";
import {
  Upload, Loader2, ScanText, FileText, RotateCcw, Copy, Check,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface Props {
  dir: "rtl" | "ltr";
}

type Phase = "idle" | "ready" | "running" | "done" | "error";

// ── Per-page canvas with bbox overlay ────────────────────────────────────────

function PageCanvas({
  page,
  pageIndex,
  selected,
  onSelect,
}: {
  page: OcrPage;
  pageIndex: number;
  selected: { page: number; index: number } | null;
  onSelect: (page: number, index: number) => void;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const imgRef    = useRef<HTMLImageElement | null>(null);

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    const img    = imgRef.current;
    if (!canvas || !img) return;
    const ctx   = canvas.getContext("2d")!;
    const scale = canvas.width / page.width;
    canvas.height = Math.round(page.height * scale);

    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);

    for (const det of page.detections) {
      const isSelected = selected?.page === pageIndex && selected?.index === det.index;
      const pts = det.bbox.map(([x, y]) => [x * scale, y * scale]);

      ctx.beginPath();
      ctx.moveTo(pts[0][0], pts[0][1]);
      for (let i = 1; i < pts.length; i++) ctx.lineTo(pts[i][0], pts[i][1]);
      ctx.closePath();

      ctx.fillStyle   = isSelected ? "rgba(59,130,246,0.25)" : "rgba(234,179,8,0.10)";
      ctx.strokeStyle = isSelected ? "#3B82F6" : "#D97706";
      ctx.lineWidth   = isSelected ? 2.5 : 1.5;
      ctx.fill();
      ctx.stroke();
    }
  }, [page, pageIndex, selected]);

  // Load image once, then draw
  useEffect(() => {
    const img = new Image();
    img.onload = () => { imgRef.current = img; draw(); };
    img.src = `data:image/jpeg;base64,${page.image_b64}`;
  }, [page.image_b64]);   // eslint-disable-line react-hooks/exhaustive-deps

  // Redraw whenever selection changes
  useEffect(() => { if (imgRef.current) draw(); }, [draw]);

  const handleClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const sx   = page.width  / canvas.width;
    const sy   = page.height / canvas.height;
    const cx   = (e.clientX - rect.left) * sx;
    const cy   = (e.clientY - rect.top)  * sy;

    for (const det of page.detections) {
      const xs = det.bbox.map(p => p[0]);
      const ys = det.bbox.map(p => p[1]);
      if (cx >= Math.min(...xs) && cx <= Math.max(...xs) &&
          cy >= Math.min(...ys) && cy <= Math.max(...ys)) {
        onSelect(pageIndex, det.index);
        return;
      }
    }
    onSelect(-1, -1);  // click outside — deselect
  };

  return (
    <canvas
      ref={canvasRef}
      width={900}
      className="w-full cursor-crosshair block"
      onClick={handleClick}
    />
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function OcrStagePage({ dir }: Props) {
  const [file, setFile]         = useState<File | null>(null);
  const [fileUrl, setFileUrl]   = useState<string | null>(null);
  const [phase, setPhase]       = useState<Phase>("idle");
  const [dragging, setDragging] = useState(false);
  const [result, setResult]     = useState<OcrResult | null>(null);
  const [selected, setSelected] = useState<{ page: number; index: number } | null>(null);
  const [copied, setCopied]     = useState(false);
  const [backend, setBackend]   = useState<LocalOcrBackend>("paddleocr");

  const { data: ocrConfigData } = useQuery({
    queryKey: ["ocr-config"],
    queryFn: () => getOcrConfig().then(r => r.data.paddleocr),
    staleTime: Infinity,
  });

  const [editedParams, setEditedParams] = useState<Record<string, unknown>>({});

  useEffect(() => {
    if (!ocrConfigData) return;
    setEditedParams(prev => {
      if (Object.keys(prev).length > 0) return prev;
      const { show_log: _, ...rest } = ocrConfigData as Record<string, unknown> & { show_log?: unknown };
      return rest;
    });
  }, [ocrConfigData]);

  const isParamsDirty = ocrConfigData && Object.entries(editedParams).some(
    ([k, v]) => (ocrConfigData as Record<string, unknown>)[k] !== v
  );

  const resetParams = () => {
    if (!ocrConfigData) return;
    const { show_log: _, ...rest } = ocrConfigData as Record<string, unknown> & { show_log?: unknown };
    setEditedParams(rest);
  };

  const detRefs = useRef<Map<string, HTMLDivElement>>(new Map());

  const ocrMutation = useMutation({
    mutationFn: (f: File) => runOcr(f, backend, Object.keys(editedParams).length ? editedParams : undefined).then(r => r.data),
    onSuccess: (data) => { setResult(data); setPhase("done"); },
    onError:   ()     => setPhase("error"),
  });

  const handleFile = useCallback((f: File) => {
    if (fileUrl) URL.revokeObjectURL(fileUrl);
    setFile(f);
    setFileUrl(URL.createObjectURL(f));
    setPhase("ready");
    setResult(null);
    setSelected(null);
  }, [fileUrl]);

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault(); setDragging(false);
    const f = e.dataTransfer.files[0];
    if (f) handleFile(f);
  };

  const handleRun = () => {
    if (!file) return;
    setPhase("running");
    setSelected(null);
    ocrMutation.mutate(file);
  };

  const handleReset = () => {
    if (fileUrl) URL.revokeObjectURL(fileUrl);
    setFile(null); setFileUrl(null); setResult(null);
    setPhase("idle"); setSelected(null); setCopied(false);
  };

  // Canvas clicks → scroll detection list to match
  const handleCanvasSelect = (pageIdx: number, detIdx: number) => {
    if (pageIdx < 0) { setSelected(null); return; }
    setSelected({ page: pageIdx, index: detIdx });
    const el = detRefs.current.get(`${pageIdx}-${detIdx}`);
    el?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  };

  // Detection list clicks → update canvas highlight
  const handleListSelect = (pageIdx: number, detIdx: number) => {
    setSelected({ page: pageIdx, index: detIdx });
  };

  const handleCopy = () => {
    if (!result?.text) return;
    navigator.clipboard.writeText(result.text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const allDetections = result?.pages.flatMap((p, pi) =>
    p.detections.map(d => ({ ...d, pageIndex: pi }))
  ) ?? [];

  const hasFile   = !!file;
  const isRunning = phase === "running";

  return (
    <div className="flex h-screen overflow-hidden">

      {/* ── Left: document / canvas ─────────────────────────────────────────── */}
      <div
        className="shrink-0 overflow-hidden border-r bg-muted/10 transition-[width,opacity] duration-700 ease-out"
        style={{ width: hasFile ? "50%" : "0%", opacity: hasFile ? 1 : 0 }}
      >
        {file && (
          <div className="flex flex-col h-full">
            {/* Header */}
            <div className="h-12 px-4 border-b bg-white flex items-center gap-2 shrink-0">
              <FileText className="w-4 h-4 text-muted-foreground shrink-0" />
              <span className="text-sm font-medium truncate flex-1">{file.name}</span>
              {result && (
                <span className="text-xs text-muted-foreground shrink-0 font-mono">
                  {result.backend} · {result.latency_ms} ms
                </span>
              )}
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto bg-muted/20">

              {/* Before OCR: plain preview */}
              {!result && phase !== "running" && fileUrl && (
                <div className="p-4 h-full">
                  {file.type === "application/pdf" ? (
                    <iframe src={fileUrl} className="w-full h-full min-h-[600px] border-none rounded-xl" title="Preview" />
                  ) : (
                    <img src={fileUrl} alt="Preview" className="max-w-full object-contain rounded-xl shadow mx-auto" />
                  )}
                </div>
              )}

              {/* Running spinner */}
              {phase === "running" && (
                <div className="flex flex-col items-center justify-center h-full gap-3 text-muted-foreground py-20">
                  <Loader2 className="w-8 h-8 animate-spin" />
                  <p className="text-sm">{dir === "rtl" ? "جارٍ التحليل..." : "Analysing..."}</p>
                </div>
              )}

              {/* After OCR: canvas pages with bbox overlay */}
              {result && (
                <div className="p-4 space-y-4">
                  {result.pages.length === 0 && (
                    <p className="text-sm text-muted-foreground italic p-4">
                      {dir === "rtl" ? "لا توجد صور في النتيجة" : "No page images in result"}
                    </p>
                  )}
                  {result.pages.map((page, pi) => (
                    <div key={pi} className="rounded-xl overflow-hidden shadow-sm border bg-white">
                      {result.pages.length > 1 && (
                        <div className="px-3 py-1.5 text-xs text-muted-foreground border-b bg-muted/30 font-medium">
                          {dir === "rtl" ? `صفحة ${pi + 1}` : `Page ${pi + 1}`}
                        </div>
                      )}
                      <PageCanvas
                        page={page}
                        pageIndex={pi}
                        selected={selected}
                        onSelect={handleCanvasSelect}
                      />
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* ── Right: upload / controls / detection list ────────────────────────── */}
      <div className="flex-1 min-w-0 flex flex-col overflow-hidden">

        {/* IDLE: upload zone */}
        {phase === "idle" && (
          <div className="flex-1 flex items-center justify-center p-8">
            <label
              className={cn(
                "flex flex-col items-center gap-6 p-16 border-2 border-dashed rounded-2xl cursor-pointer",
                "transition-all duration-300 max-w-sm w-full select-none",
                dragging
                  ? "border-primary bg-primary/5 scale-[1.03] shadow-lg"
                  : "border-border hover:border-primary/60 hover:bg-muted/30 hover:shadow-sm"
              )}
              onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
              onDragLeave={() => setDragging(false)}
              onDrop={handleDrop}
            >
              <div className={cn(
                "w-24 h-24 rounded-full flex items-center justify-center transition-all duration-300",
                dragging ? "bg-primary/15 scale-110" : "bg-muted"
              )}>
                <Upload className={cn("w-10 h-10 transition-colors", dragging ? "text-primary" : "text-muted-foreground")} />
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
                onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f); e.target.value = ""; }}
              />
            </label>
          </div>
        )}

        {/* READY / RUNNING / DONE / ERROR */}
        {phase !== "idle" && (
          <div className="flex-1 flex flex-col overflow-hidden">

            {/* Scrollable: detection list */}
            <div className="flex-1 overflow-y-auto p-6 space-y-2">

              {/* Header row */}
              <div className="flex items-center gap-2 mb-3">
                <ScanText className="w-4 h-4 text-muted-foreground" />
                <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
                  {dir === "rtl" ? "نتائج التعرف الضوئي" : "OCR Detections"}
                </h2>
                {phase === "done" && (
                  <span className="ms-auto text-xs text-muted-foreground bg-muted px-2 py-0.5 rounded font-mono">
                    {allDetections.length} {dir === "rtl" ? "نص" : "texts"}
                  </span>
                )}
              </div>

              {/* States */}
              {phase === "ready" && (
                <div className="flex items-center justify-center h-40 text-muted-foreground/60 text-sm">
                  {dir === "rtl" ? "اضغط «تشغيل» لبدء التعرف" : "Press Run OCR to begin"}
                </div>
              )}

              {phase === "running" && (
                <div className="flex flex-col items-center justify-center h-40 gap-3 text-muted-foreground">
                  <Loader2 className="w-6 h-6 animate-spin" />
                  <p className="text-sm">{dir === "rtl" ? "جارٍ الاستخراج..." : "Extracting text..."}</p>
                </div>
              )}

              {phase === "error" && (
                <div className="p-4 rounded-xl bg-destructive/10 text-destructive text-sm">
                  {dir === "rtl" ? "فشل استخراج النص" : "OCR failed — check console"}
                </div>
              )}

              {/* Detection cards */}
              {phase === "done" && allDetections.map((det, gi) => {
                const isSelected = selected?.page === det.pageIndex && selected?.index === det.index;
                const key = `${det.pageIndex}-${det.index}`;
                return (
                  <div
                    key={gi}
                    ref={el => { if (el) detRefs.current.set(key, el); else detRefs.current.delete(key); }}
                    onClick={() => handleListSelect(det.pageIndex, det.index)}
                    className={cn(
                      "flex items-start gap-3 p-3 rounded-xl border cursor-pointer transition-all duration-150",
                      isSelected
                        ? "border-primary/50 bg-primary/5 shadow-sm"
                        : "border-border bg-white hover:border-primary/30 hover:bg-muted/20"
                    )}
                  >
                    {/* Confidence badge */}
                    <span className={cn(
                      "shrink-0 text-xs font-medium px-1.5 py-0.5 rounded-md tabular-nums",
                      det.confidence >= 0.8 ? "bg-green-100 text-green-700" : "bg-amber-100 text-amber-700"
                    )}>
                      {Math.round(det.confidence * 100)}%
                    </span>

                    {/* Text */}
                    <p className="text-sm leading-relaxed flex-1 break-words font-mono" dir="auto">
                      {det.text}
                    </p>

                    {/* Page indicator (multi-page only) */}
                    {result!.pages.length > 1 && (
                      <span className="shrink-0 text-xs text-muted-foreground/60">
                        p{det.pageIndex + 1}
                      </span>
                    )}
                  </div>
                );
              })}
            </div>

            {/* Sticky bottom: backend selector + run / copy / reset */}
            <div className="border-t bg-white px-6 py-5 space-y-3 shrink-0">

              {/* Backend selector */}
              <div className="space-y-1.5">
                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                  {dir === "rtl" ? "محرك التعرف" : "OCR Engine"}
                </p>
                <div className="flex gap-2">
                  {LOCAL_OCR_BACKENDS.map(b => (
                    <button
                      key={b}
                      onClick={() => { setBackend(b); setEditedParams({}); }}
                      disabled={isRunning}
                      className={cn(
                        "px-3 py-1.5 rounded-lg border text-xs font-mono font-medium transition-all",
                        backend === b
                          ? "border-primary bg-primary/10 text-primary shadow-sm"
                          : "border-border text-muted-foreground hover:border-primary/40 hover:text-foreground"
                      )}
                    >
                      {b}
                    </button>
                  ))}
                </div>
              </div>

              {/* PaddleOCR parameters */}
              {backend === "paddleocr" && Object.keys(editedParams).length > 0 && (
                <div className="space-y-1.5">
                  <div className="flex items-center gap-2">
                    <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider flex-1">
                      {dir === "rtl" ? "معاملات PaddleOCR" : "PaddleOCR Parameters"}
                    </p>
                    {isParamsDirty && (
                      <button
                        onClick={resetParams}
                        className="text-xs text-amber-600 hover:text-amber-700 font-medium transition-colors"
                      >
                        {dir === "rtl" ? "إعادة تعيين" : "Reset"}
                      </button>
                    )}
                  </div>
                  <div className="rounded-lg border bg-muted/30 divide-y text-xs font-mono">
                    {Object.entries(editedParams).map(([key, val]) => (
                      <div key={key} className="flex items-center px-3 py-1.5 gap-3">
                        <span className="text-muted-foreground shrink-0 w-40">{key}</span>

                        {typeof val === "boolean" ? (
                          <button
                            disabled={isRunning}
                            onClick={() => setEditedParams(p => ({ ...p, [key]: !val }))}
                            className={cn(
                              "font-semibold transition-colors",
                              val ? "text-green-600 hover:text-green-700" : "text-red-500 hover:text-red-600",
                              isRunning && "opacity-40 cursor-not-allowed"
                            )}
                          >
                            {String(val)}
                          </button>
                        ) : typeof val === "number" ? (
                          <input
                            type="number"
                            value={val}
                            disabled={isRunning}
                            step={val < 2 ? 0.05 : 0.25}
                            min={0}
                            onChange={e => {
                              const n = parseFloat(e.target.value);
                              if (!isNaN(n)) setEditedParams(p => ({ ...p, [key]: n }));
                            }}
                            className={cn(
                              "w-20 font-semibold bg-transparent border-b border-border",
                              "focus:outline-none focus:border-primary transition-colors",
                              isRunning && "opacity-40 cursor-not-allowed"
                            )}
                          />
                        ) : (
                          <input
                            type="text"
                            value={String(val)}
                            disabled={isRunning}
                            onChange={e => setEditedParams(p => ({ ...p, [key]: e.target.value }))}
                            className={cn(
                              "w-20 font-semibold bg-transparent border-b border-border",
                              "focus:outline-none focus:border-primary transition-colors",
                              isRunning && "opacity-40 cursor-not-allowed"
                            )}
                          />
                        )}

                        {/* dirty indicator */}
                        {ocrConfigData && (ocrConfigData as Record<string, unknown>)[key] !== val && (
                          <span className="text-amber-500 text-[10px]">●</span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <button
                onClick={handleRun}
                disabled={!file || isRunning || phase === "done"}
                className={cn(
                  "w-full flex items-center justify-center gap-2 py-3 rounded-xl font-semibold text-sm",
                  "bg-primary text-primary-foreground hover:bg-primary/90 transition-all duration-200",
                  "disabled:opacity-40 disabled:cursor-not-allowed shadow-sm hover:shadow"
                )}
              >
                {isRunning
                  ? <><Loader2 className="w-4 h-4 animate-spin" />{dir === "rtl" ? "جارٍ التشغيل..." : "Running..."}</>
                  : phase === "done"
                  ? <><Check className="w-4 h-4" />{dir === "rtl" ? "اكتمل الاستخراج" : "Extraction complete"}</>
                  : <><ScanText className="w-4 h-4" />{dir === "rtl" ? "تشغيل OCR" : "Run OCR"}</>
                }
              </button>

              {phase === "done" && result?.text && (
                <button
                  onClick={handleCopy}
                  className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl border text-sm text-muted-foreground hover:text-foreground hover:border-primary/40 transition-colors"
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
