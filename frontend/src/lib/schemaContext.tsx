import { createContext, useContext, useState, useCallback, ReactNode } from "react";

export type SchemaSource = "default" | "custom";

interface SchemaContextValue {
  source: SchemaSource;
  password: string;        // for default schema (persisted in sessionStorage)
  customToken: string;     // token returned after uploading a custom schema
  customName: string;      // display name for the uploaded file
  setPassword: (p: string) => void;
  setCustomSchema: (token: string, name: string) => void;
  clearCustomSchema: () => void;
}

const SchemaContext = createContext<SchemaContextValue | null>(null);

const SESSION_KEY = "mawrid_schema_pwd";

export function SchemaProvider({ children }: { children: ReactNode }) {
  const [password, _setPassword] = useState<string>(
    () => sessionStorage.getItem(SESSION_KEY) ?? ""
  );
  const [customToken, setCustomToken] = useState("");
  const [customName, setCustomName] = useState("");

  const setPassword = useCallback((p: string) => {
    _setPassword(p);
    if (p) sessionStorage.setItem(SESSION_KEY, p);
    else sessionStorage.removeItem(SESSION_KEY);
  }, []);

  const setCustomSchema = useCallback((token: string, name: string) => {
    setCustomToken(token);
    setCustomName(name);
  }, []);

  const clearCustomSchema = useCallback(() => {
    setCustomToken("");
    setCustomName("");
  }, []);

  const source: SchemaSource = customToken ? "custom" : "default";

  return (
    <SchemaContext.Provider value={{ source, password, customToken, customName, setPassword, setCustomSchema, clearCustomSchema }}>
      {children}
    </SchemaContext.Provider>
  );
}

export function useSchemaCtx() {
  const ctx = useContext(SchemaContext);
  if (!ctx) throw new Error("useSchemaCtx must be used inside SchemaProvider");
  return ctx;
}
