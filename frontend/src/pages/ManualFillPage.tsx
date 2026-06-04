import { useState, useCallback } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { getSchema, saveDocument, buildUICategories, UIField, UICategory } from "@/lib/api";
import { Save, CheckCircle2, Loader2, FileText, ChevronDown, Upload, X } from "lucide-react";
import { cn } from "@/lib/utils";

interface Props { dir: "rtl" | "ltr" }

function FieldInput({
  field, value, onChange,
}: {
  field: UIField; value: string; onChange: (v: string) => void;
}) {
  const base =
    "w-full px-3 py-2 border rounded-lg text-sm bg-white " +
    "focus:outline-none focus:ring-2 focus:ring-primary/30 transition-colors";

  if (field.type === "lookup" && field.options?.length) {
    return (
      <select value={value} onChange={e => onChange(e.target.value)} className={cn(base, "cursor-pointer")}>
        <option value="">—</option>
        {field.options.map(opt => <option key={opt} value={opt}>{opt}</option>)}
      </select>
    );
  }
  if (field.type === "date")   return <input type="date"   value={value} onChange={e => onChange(e.target.value)} className={base} />;
  if (field.type === "number") return <input type="number" value={value} onChange={e => onChange(e.target.value)} className={base} />;
  return <input type="text" value={value} onChange={e => onChange(e.target.value)} className={base} />;
}

function SelectBox({
  label, value, onChange, children, disabled,
}: {
  label: string; value: string; onChange: (v: string) => void;
  children: React.ReactNode; disabled?: boolean;
}) {
  return (
    <div className="space-y-1.5">
      <label className="block text-xs font-semibold text-muted-foreground uppercase tracking-wide">
        {label}
      </label>
      <div className="relative">
        <select
          value={value}
          onChange={e => onChange(e.target.value)}
          disabled={disabled}
          className={cn(
            "w-full appearance-none px-3 py-2.5 pr-8 border rounded-xl text-sm bg-white",
            "focus:outline-none focus:ring-2 focus:ring-primary/30 transition-colors",
            "disabled:opacity-50 disabled:cursor-not-allowed",
            value ? "text-foreground font-medium" : "text-muted-foreground"
          )}
          dir="rtl"
        >
          {children}
        </select>
        <ChevronDown className="absolute end-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground pointer-events-none" />
      </div>
    </div>
  );
}

export default function ManualFillPage({ dir }: Props) {
  const qc = useQueryClient();

  const { data: schemaData, isLoading: schemaLoading } = useQuery({
    queryKey: ["schema"],
    queryFn:  () => getSchema().then(r => r.data),
    staleTime: Infinity,
  });

  const categories: UICategory[] = schemaData ? buildUICategories(schemaData) : [];

  const [filterCat, setFilterCat]       = useState("");
  const [selectedType, setSelectedType] = useState("");
  const [fieldValues, setFieldValues]   = useState<Record<string, string>>({});
  const [saved, setSaved]               = useState(false);

  const [file, setFile]       = useState<File | null>(null);
  const [fileUrl, setFileUrl] = useState<string | null>(null);
  const [dragging, setDrag]   = useState(false);

  // category is derived from the selected doc type — filterCat is just a UI filter
  const derivedCat = selectedType ? (schemaData?.documents[selectedType]?.category ?? "") : "";
  const activeCat  = categories.find(c => c.id === (filterCat || derivedCat));
  const activeType = categories.flatMap(c => c.types).find(t => t.id === selectedType);
  const fields     = activeType?.fields ?? [];

  // Types shown in the picker: all types when no filter, filtered when cat chosen
  const visibleTypes = filterCat
    ? (categories.find(c => c.id === filterCat)?.types ?? [])
    : categories.flatMap(c => c.types);

  const handleFilterCatChange = (cat: string) => {
    setFilterCat(cat);
    // clear selected type only if it doesn't belong to the new filter
    if (cat && selectedType && schemaData?.documents[selectedType]?.category !== cat) {
      setSelectedType(""); setFieldValues({}); setSaved(false);
    }
  };
  const handleTypeChange = (type: string) => {
    setSelectedType(type); setFieldValues({}); setSaved(false);
  };

  const handleFile = useCallback((f: File) => {
    if (fileUrl) URL.revokeObjectURL(fileUrl);
    setFile(f);
    setFileUrl(URL.createObjectURL(f));
  }, [fileUrl]);

  const removeFile = () => {
    if (fileUrl) URL.revokeObjectURL(fileUrl);
    setFile(null); setFileUrl(null);
  };

  const handleReset = () => { setFieldValues({}); setSaved(false); };

  const saveMutation = useMutation({
    mutationFn: () => {
      const catLabel  = schemaData?._categories?.[derivedCat]?.label_ar ?? derivedCat;
      const typeLabel = activeType?.labelAr ?? selectedType;
      const uploadFile = file ?? new File(["manual"], `manual-${selectedType}.txt`, { type: "text/plain" });
      return saveDocument({
        file:          uploadFile,
        category:      derivedCat,
        categoryLabel: catLabel,
        docType:       selectedType,
        docTypeLabel:  typeLabel,
        combo:         "manual",
        confidence:    1.0,
        cost:          0,
        latency:       0,
        fields: fields.map(f => ({
          field_id:   f.id,
          label_ar:   f.labelAr,
          value:      fieldValues[f.id] ?? null,
          confidence: 1.0,
        })),
      });
    },
    onSuccess: () => {
      setSaved(true);
      qc.invalidateQueries({ queryKey: ["saved-documents"] });
    },
  });

  const canSave = !!selectedType && fields.length > 0 && !saved;

  return (
    <div className="flex h-screen overflow-hidden" dir={dir}>

      {/* ── Left panel: type picker + file upload ──────────────────────── */}
      <div className="w-72 shrink-0 border-e bg-white flex flex-col h-screen overflow-hidden">
        <div className="px-5 pt-6 pb-4 border-b shrink-0">
          <h1 className="text-base font-bold text-foreground">
            {dir === "rtl" ? "تعبئة يدوية" : "Manual Entry"}
          </h1>
          <p className="text-xs text-muted-foreground mt-1 leading-relaxed">
            {dir === "rtl"
              ? "اختر نوع الوثيقة وعبّئ الحقول يدوياً"
              : "Select a document type and fill fields manually"}
          </p>
        </div>

        <div className="flex-1 overflow-y-auto p-5 space-y-4">
          {schemaLoading && (
            <div className="flex items-center justify-center py-10 text-muted-foreground">
              <Loader2 className="w-5 h-5 animate-spin" />
            </div>
          )}

          {!schemaLoading && (
            <>
              <SelectBox
                label={dir === "rtl" ? "الفئة" : "Category"}
                value={selectedCat}
                onChange={handleCatChange}
              >
                <option value="">{dir === "rtl" ? "— اختر الفئة —" : "— Choose category —"}</option>
                {categories.map(c => (
                  <option key={c.id} value={c.id}>{c.labelAr}</option>
                ))}
              </SelectBox>

              <SelectBox
                label={dir === "rtl" ? "نوع الوثيقة" : "Document Type"}
                value={selectedType}
                onChange={handleTypeChange}
                disabled={!selectedCat}
              >
                <option value="">{dir === "rtl" ? "— اختر النوع —" : "— Choose type —"}</option>
                {activeCat?.types.map(t => (
                  <option key={t.id} value={t.id}>{t.labelAr}</option>
                ))}
              </SelectBox>

              {activeType && (
                <div className="flex items-center gap-2 py-2 px-3 rounded-lg bg-primary/5 border border-primary/20">
                  <FileText className="w-4 h-4 text-primary shrink-0" />
                  <div className="min-w-0">
                    <p className="text-xs font-semibold text-primary truncate" dir="rtl">{activeType.labelAr}</p>
                    <p className="text-xs text-muted-foreground">{fields.length} {dir === "rtl" ? "حقل" : "fields"}</p>
                  </div>
                </div>
              )}

              {/* ── File upload ─────────────────────────────────────────── */}
              <div className="pt-2 border-t space-y-2">
                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                  {dir === "rtl" ? "إرفاق الوثيقة (اختياري)" : "Attach Document (optional)"}
                </p>

                {!file ? (
                  <label
                    className={cn(
                      "flex flex-col items-center gap-2 p-4 border-2 border-dashed rounded-xl cursor-pointer",
                      "transition-all duration-200 select-none",
                      dragging
                        ? "border-primary bg-primary/5"
                        : "border-border hover:border-primary/50 hover:bg-muted/30"
                    )}
                    onDragOver={e => { e.preventDefault(); setDrag(true); }}
                    onDragLeave={() => setDrag(false)}
                    onDrop={e => { e.preventDefault(); setDrag(false); const f = e.dataTransfer.files[0]; if (f) handleFile(f); }}
                  >
                    <Upload className={cn("w-5 h-5", dragging ? "text-primary" : "text-muted-foreground")} />
                    <span className="text-xs text-muted-foreground text-center">
                      {dir === "rtl" ? "اسحب أو انقر للرفع" : "Drag & drop or click"}
                    </span>
                    <span className="text-[10px] text-muted-foreground/60">PDF · PNG · JPG</span>
                    <input
                      type="file"
                      accept=".pdf,.png,.jpg,.jpeg,.tiff"
                      className="hidden"
                      onChange={e => { const f = e.target.files?.[0]; if (f) handleFile(f); e.target.value = ""; }}
                    />
                  </label>
                ) : (
                  <div className="flex items-center gap-2 px-3 py-2.5 rounded-xl border bg-muted/20">
                    <FileText className="w-4 h-4 text-muted-foreground shrink-0" />
                    <span className="text-xs text-foreground truncate flex-1 font-medium">{file.name}</span>
                    <button
                      onClick={removeFile}
                      className="text-muted-foreground hover:text-destructive transition-colors shrink-0"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </div>

      {/* ── Document preview (slides in when file is attached) ─────────── */}
      <div
        className="shrink-0 overflow-hidden border-e bg-muted/10 transition-[width,opacity] duration-700 ease-out"
        style={{ width: file ? "40%" : "0%", opacity: file ? 1 : 0 }}
      >
        {file && fileUrl && (
          <div className="flex flex-col h-full">
            <div className="h-11 px-4 border-b bg-white flex items-center gap-2 shrink-0">
              <FileText className="w-4 h-4 text-muted-foreground shrink-0" />
              <span className="text-sm font-medium truncate flex-1">{file.name}</span>
              <span className="text-xs text-muted-foreground shrink-0">
                {(file.size / 1024).toFixed(0)} KB
              </span>
            </div>
            <div className="flex-1 overflow-hidden">
              {file.type === "application/pdf"
                ? <iframe src={fileUrl} className="w-full h-full border-none" title="Document preview" />
                : (
                  <div className="h-full flex items-center justify-center p-4 bg-muted/20">
                    <img src={fileUrl} alt="Document preview"
                      className="max-h-full max-w-full object-contain rounded-xl shadow" />
                  </div>
                )
              }
            </div>
          </div>
        )}
      </div>

      {/* ── Right panel: form ────────────────────────────────────────────── */}
      <div className="flex-1 min-w-0 flex flex-col overflow-hidden bg-muted/10">

        {!activeType && (
          <div className="flex-1 flex flex-col items-center justify-center text-muted-foreground gap-4 p-8">
            <div className="w-20 h-20 rounded-2xl bg-muted flex items-center justify-center">
              <FileText className="w-9 h-9 text-muted-foreground/50" />
            </div>
            <div className="text-center">
              <p className="font-medium text-sm">
                {dir === "rtl" ? "اختر نوع الوثيقة للبدء" : "Select a document type to begin"}
              </p>
              <p className="text-xs text-muted-foreground/70 mt-1">
                {dir === "rtl" ? "ستظهر الحقول هنا" : "Fields will appear here"}
              </p>
            </div>
          </div>
        )}

        {activeType && (
          <div className="flex-1 flex flex-col overflow-hidden">
            <div className="px-8 py-5 border-b bg-white shrink-0">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="font-bold text-lg" dir="rtl">{activeType.labelAr}</h2>
                  <p className="text-sm text-muted-foreground mt-0.5">
                    {activeCat?.labelAr}
                    <span className="mx-2 opacity-30">·</span>
                    {fields.length} {dir === "rtl" ? "حقل" : "fields"}
                  </p>
                </div>
                {saved && (
                  <div className="flex items-center gap-2 text-emerald-600 text-sm font-medium">
                    <CheckCircle2 className="w-5 h-5" />
                    {dir === "rtl" ? "تم الحفظ" : "Saved"}
                  </div>
                )}
              </div>
            </div>

            <div className="flex-1 overflow-y-auto px-8 py-6">
              <div className="max-w-2xl space-y-5">
                {fields.map(field => (
                  <div key={field.id} className="space-y-1.5">
                    <label className="block text-sm font-medium text-foreground" dir="rtl">
                      {field.labelAr}
                      {field.required && <span className="text-destructive ms-0.5">*</span>}
                    </label>
                    <FieldInput
                      field={field}
                      value={fieldValues[field.id] ?? ""}
                      onChange={v => setFieldValues(prev => ({ ...prev, [field.id]: v }))}
                    />
                  </div>
                ))}
              </div>
            </div>

            <div className="border-t bg-white px-8 py-4 flex items-center gap-3 shrink-0">
              <button
                onClick={handleReset}
                disabled={saveMutation.isPending}
                className="px-4 py-2.5 rounded-xl border text-sm font-medium text-muted-foreground hover:bg-muted transition-colors disabled:opacity-40"
              >
                {dir === "rtl" ? "مسح" : "Clear"}
              </button>

              <button
                onClick={() => saveMutation.mutate()}
                disabled={!canSave || saveMutation.isPending}
                className={cn(
                  "flex items-center gap-2 px-6 py-2.5 rounded-xl font-semibold text-sm transition-all duration-200",
                  "bg-emerald-600 text-white hover:bg-emerald-700 shadow-sm hover:shadow",
                  "disabled:opacity-40 disabled:cursor-not-allowed"
                )}
              >
                {saveMutation.isPending
                  ? <><Loader2 className="w-4 h-4 animate-spin" />{dir === "rtl" ? "جارٍ الحفظ..." : "Saving..."}</>
                  : <><Save className="w-4 h-4" />{dir === "rtl" ? "حفظ السجل" : "Save Record"}</>
                }
              </button>

              {saveMutation.isError && (
                <p className="text-xs text-destructive ms-2">
                  {dir === "rtl" ? "فشل الحفظ" : "Save failed"}
                </p>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
