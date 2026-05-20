import { useCallback, useState } from "react";
import { Upload, FileText, X } from "lucide-react";
import { cn } from "@/lib/utils";

interface Props {
  onFile: (file: File) => void;
  disabled?: boolean;
  dir: "rtl" | "ltr";
}

export default function DocumentUploader({ onFile, disabled, dir }: Props) {
  const [dragging, setDragging] = useState(false);
  const [selected, setSelected] = useState<File | null>(null);

  const handleFile = useCallback(
    (file: File) => {
      setSelected(file);
      onFile(file);
    },
    [onFile]
  );

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  };

  return (
    <div className="space-y-3">
      <label
        className={cn(
          "flex flex-col items-center justify-center gap-3 border-2 border-dashed rounded-xl p-8 cursor-pointer transition-all",
          dragging
            ? "border-primary bg-primary/5 scale-[1.01]"
            : "border-border hover:border-primary/50 hover:bg-muted/30",
          disabled && "opacity-50 cursor-not-allowed"
        )}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
      >
        <div
          className={cn(
            "p-3 rounded-full transition-colors",
            dragging ? "bg-primary/10" : "bg-muted"
          )}
        >
          <Upload
            className={cn(
              "w-6 h-6 transition-colors",
              dragging ? "text-primary" : "text-muted-foreground"
            )}
          />
        </div>
        <div className="text-center">
          <p className="text-sm font-medium">
            {dir === "rtl"
              ? "اسحب الملف هنا أو انقر للاختيار"
              : "Drag file here or click to select"}
          </p>
          <p className="text-xs text-muted-foreground mt-1">
            PDF, PNG, JPG — {dir === "rtl" ? "حتى 20 ميغابايت" : "up to 20 MB"}
          </p>
        </div>
        <input
          id="file-input"
          type="file"
          accept=".pdf,.png,.jpg,.jpeg,.tiff"
          className="hidden"
          disabled={disabled}
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) handleFile(file);
          }}
        />
      </label>

      {selected && (
        <div className="flex items-center gap-2 px-3 py-2 bg-muted rounded-lg text-sm">
          <FileText className="w-4 h-4 text-muted-foreground shrink-0" />
          <span className="flex-1 truncate text-foreground">{selected.name}</span>
          <span className="text-muted-foreground text-xs shrink-0">
            {(selected.size / 1024).toFixed(0)} KB
          </span>
          <button
            onClick={(e) => {
              e.stopPropagation();
              setSelected(null);
            }}
            className="text-muted-foreground hover:text-foreground"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}
    </div>
  );
}
