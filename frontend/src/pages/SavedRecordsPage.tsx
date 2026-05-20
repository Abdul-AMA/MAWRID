import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getSavedDocuments, deleteSavedDocument, SavedDocumentRecord } from "@/lib/api";
import { Trash2, ChevronDown, ChevronUp, FileText, Archive, ExternalLink, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

interface Props {
  dir: "rtl" | "ltr";
}

export default function SavedRecordsPage({ dir }: Props) {
  const qc = useQueryClient();
  const [expanded, setExpanded] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["saved-documents"],
    queryFn: () => getSavedDocuments().then((r) => r.data),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteSavedDocument(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["saved-documents"] }),
  });

  const records: SavedDocumentRecord[] = data?.records ?? [];

  if (isLoading) {
    return (
      <div className="h-full flex items-center justify-center">
        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (records.length === 0) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center space-y-3">
          <div className="w-16 h-16 rounded-2xl bg-muted flex items-center justify-center mx-auto">
            <Archive className="w-7 h-7 text-muted-foreground" />
          </div>
          <p className="font-semibold text-base">
            {dir === "rtl" ? "لا توجد سجلات محفوظة" : "No saved records yet"}
          </p>
          <p className="text-sm text-muted-foreground max-w-xs">
            {dir === "rtl"
              ? "عالج وثيقة واحفظها لتظهر هنا"
              : "Process a document and save it to see it here"}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-3xl mx-auto px-6 py-8 space-y-4">
        <div className="flex items-baseline justify-between">
          <h1 className="text-xl font-bold">
            {dir === "rtl" ? "السجلات المحفوظة" : "Saved Records"}
          </h1>
          <span className="text-sm text-muted-foreground">
            {data?.total ?? records.length}{" "}
            {dir === "rtl" ? "سجل" : "records"}
          </span>
        </div>

        <div className="space-y-2">
          {records.map((record) => (
            <RecordCard
              key={record.id}
              record={record}
              dir={dir}
              expanded={expanded === record.id}
              onToggle={() => setExpanded((p) => (p === record.id ? null : record.id))}
              onDelete={() => deleteMutation.mutate(record.id)}
              deleting={deleteMutation.isPending && deleteMutation.variables === record.id}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

function RecordCard({
  record,
  dir,
  expanded,
  onToggle,
  onDelete,
  deleting,
}: {
  record: SavedDocumentRecord;
  dir: "rtl" | "ltr";
  expanded: boolean;
  onToggle: () => void;
  onDelete: () => void;
  deleting: boolean;
}) {
  const confPct = Math.round(record.confidence * 100);
  const confColor =
    record.confidence >= 0.8 ? "text-emerald-600"
    : record.confidence >= 0.6 ? "text-amber-500"
    : record.confidence > 0 ? "text-destructive"
    : "text-muted-foreground";

  const fileUrl = `/api/saved/${record.id}/file`;

  return (
    <div className="border rounded-xl bg-white overflow-hidden shadow-sm">
      {/* Header row */}
      <div
        className="flex items-center gap-3 px-4 py-3.5 cursor-pointer hover:bg-muted/20 transition-colors"
        onClick={onToggle}
      >
        <div className="w-9 h-9 rounded-xl bg-primary/10 flex items-center justify-center shrink-0">
          <FileText className="w-4 h-4 text-primary" />
        </div>

        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold truncate">{record.filename}</p>
          <p className="text-xs text-muted-foreground mt-0.5">
            {record.category_label} · {record.doc_type_label}
          </p>
        </div>

        <div className="flex items-center gap-3 shrink-0">
          {record.confidence > 0 && (
            <span className={cn("text-xs font-semibold", confColor)}>
              {confPct}%
            </span>
          )}
          <span className="text-xs text-muted-foreground">
            {new Date(record.created_at).toLocaleDateString(
              dir === "rtl" ? "ar-EG" : "en-US",
              { year: "numeric", month: "short", day: "numeric" }
            )}
          </span>
          <a
            href={fileUrl}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            className="p-1 text-muted-foreground hover:text-primary transition-colors rounded"
            title={dir === "rtl" ? "فتح الملف" : "Open file"}
          >
            <ExternalLink className="w-3.5 h-3.5" />
          </a>
          <button
            onClick={(e) => { e.stopPropagation(); onDelete(); }}
            disabled={deleting}
            className="p-1 text-muted-foreground hover:text-destructive transition-colors rounded disabled:opacity-40"
            title={dir === "rtl" ? "حذف" : "Delete"}
          >
            {deleting ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Trash2 className="w-3.5 h-3.5" />
            )}
          </button>
          {expanded
            ? <ChevronUp className="w-4 h-4 text-muted-foreground" />
            : <ChevronDown className="w-4 h-4 text-muted-foreground" />
          }
        </div>
      </div>

      {/* Expanded field values */}
      {expanded && (
        <div className="border-t bg-muted/10 px-4 py-4 animate-in fade-in duration-200">
          {record.fields.length > 0 ? (
            <div className="grid grid-cols-2 gap-x-6 gap-y-3">
              {record.fields.map((field) => (
                <div key={field.field_id}>
                  <p className="text-xs text-muted-foreground">{field.label_ar}</p>
                  <p className="text-sm font-medium mt-0.5">
                    {field.value ?? (
                      <span className="text-muted-foreground italic">—</span>
                    )}
                  </p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">
              {dir === "rtl" ? "لا توجد حقول محفوظة" : "No fields saved"}
            </p>
          )}

          <div className="mt-4 pt-3 border-t flex flex-wrap gap-4 text-xs text-muted-foreground">
            {record.combo && <span>Combo: {record.combo}</span>}
            {record.cost > 0 && <span>{dir === "rtl" ? "التكلفة" : "Cost"}: ${record.cost.toFixed(4)}</span>}
            {record.latency > 0 && <span>{dir === "rtl" ? "الزمن" : "Time"}: {(record.latency / 1000).toFixed(2)}s</span>}
          </div>
        </div>
      )}
    </div>
  );
}
