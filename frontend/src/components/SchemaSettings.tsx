import { useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { uploadSchema } from "@/lib/api";
import { useSchemaCtx } from "@/lib/schemaContext";
import { Upload, X, Lock, FileJson, CheckCircle2, AlertCircle } from "lucide-react";
import { cn } from "@/lib/utils";

export default function SchemaSettings({ onClose }: { onClose: () => void }) {
  const ctx = useSchemaCtx();
  const fileRef = useRef<HTMLInputElement>(null);
  const [pwdInput, setPwdInput] = useState(ctx.password);
  const [pwdSaved, setPwdSaved] = useState(false);

  const uploadMut = useMutation({
    mutationFn: (file: File) => uploadSchema(file).then(r => r.data),
    onSuccess: (data, file) => {
      ctx.setCustomSchema(data.token, file.name);
    },
  });

  function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (f) uploadMut.mutate(f);
    e.target.value = "";
  }

  function savePwd() {
    ctx.setPassword(pwdInput);
    setPwdSaved(true);
    setTimeout(() => setPwdSaved(false), 2000);
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
      <div className="w-full max-w-md bg-white rounded-2xl shadow-2xl p-6 mx-4">
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-base font-semibold text-gray-900">إعدادات المخطط</h2>
          <button onClick={onClose} className="p-1 rounded-lg hover:bg-gray-100 text-gray-500">
            <X size={18} />
          </button>
        </div>

        {/* ── Password for built-in schema ── */}
        <section className="mb-6">
          <div className="flex items-center gap-2 mb-2">
            <Lock size={15} className="text-indigo-500" />
            <span className="text-sm font-medium text-gray-800">كلمة مرور المخطط الرسمي</span>
          </div>
          <p className="text-xs text-gray-500 mb-3">
            إذا كان المخطط الرسمي محميًا بكلمة مرور، أدخلها هنا. تُحفظ في الجلسة الحالية فقط.
          </p>
          <div className="flex gap-2">
            <input
              type="password"
              value={pwdInput}
              onChange={e => setPwdInput(e.target.value)}
              onKeyDown={e => e.key === "Enter" && savePwd()}
              placeholder="كلمة المرور..."
              className="flex-1 px-3 py-2 text-sm border rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-300"
            />
            <button
              onClick={savePwd}
              className="px-3 py-2 text-sm bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
            >
              {pwdSaved ? <CheckCircle2 size={15} /> : "حفظ"}
            </button>
          </div>
        </section>

        {/* ── Custom schema upload ── */}
        <section>
          <div className="flex items-center gap-2 mb-2">
            <FileJson size={15} className="text-emerald-500" />
            <span className="text-sm font-medium text-gray-800">رفع مخطط مخصص</span>
          </div>
          <p className="text-xs text-gray-500 mb-3">
            ارفع ملف JSON بنفس بنية schema_v2. سيُستخدم بدلًا من المخطط الرسمي حتى تُغلق النافذة.
          </p>

          {ctx.source === "custom" ? (
            <div className="flex items-center gap-3 p-3 rounded-lg bg-emerald-50 border border-emerald-200">
              <CheckCircle2 size={16} className="text-emerald-600 shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-emerald-800 truncate">{ctx.customName}</p>
                <p className="text-xs text-emerald-600">مخطط مخصص نشط</p>
              </div>
              <button
                onClick={ctx.clearCustomSchema}
                className="text-xs text-red-500 hover:text-red-700 whitespace-nowrap"
              >
                إزالة
              </button>
            </div>
          ) : (
            <button
              onClick={() => fileRef.current?.click()}
              disabled={uploadMut.isPending}
              className={cn(
                "w-full flex items-center justify-center gap-2 py-3 px-4 rounded-lg border-2 border-dashed",
                "text-sm text-gray-600 hover:bg-gray-50 transition-colors",
                uploadMut.isPending && "opacity-50 cursor-not-allowed",
              )}
            >
              <Upload size={16} />
              {uploadMut.isPending ? "جاري الرفع..." : "اختر ملف JSON"}
            </button>
          )}

          <input
            ref={fileRef}
            type="file"
            accept=".json"
            className="hidden"
            onChange={handleFile}
          />

          {uploadMut.isError && (
            <div className="flex items-center gap-2 mt-2 text-xs text-red-600">
              <AlertCircle size={13} />
              {(uploadMut.error as any)?.response?.data?.detail ?? "فشل رفع الملف"}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
