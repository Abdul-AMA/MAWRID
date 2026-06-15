import { useState } from "react";
import { Lock } from "lucide-react";

interface Props {
  onSubmit: (password: string) => void;
}

export default function SchemaPasswordModal({ onSubmit }: Props) {
  const [value, setValue] = useState("");

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="w-full max-w-sm bg-white rounded-2xl shadow-2xl p-8 mx-4">
        <div className="flex flex-col items-center gap-3 mb-6">
          <div className="w-12 h-12 rounded-full bg-indigo-100 flex items-center justify-center">
            <Lock size={22} className="text-indigo-600" />
          </div>
          <h2 className="text-base font-semibold text-gray-900">المخطط محمي</h2>
          <p className="text-sm text-center text-gray-500">أدخل كلمة المرور للوصول إلى مخطط الوثائق الرسمي</p>
        </div>
        <form onSubmit={e => { e.preventDefault(); if (value.trim()) onSubmit(value.trim()); }}>
          <input
            autoFocus
            type="password"
            value={value}
            onChange={e => setValue(e.target.value)}
            placeholder="كلمة المرور..."
            className="w-full px-4 py-3 text-sm border rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-300 mb-4"
          />
          <button
            type="submit"
            disabled={!value.trim()}
            className="w-full py-3 bg-indigo-600 text-white text-sm font-medium rounded-xl hover:bg-indigo-700 transition-colors disabled:opacity-50"
          >
            دخول
          </button>
        </form>
      </div>
    </div>
  );
}
