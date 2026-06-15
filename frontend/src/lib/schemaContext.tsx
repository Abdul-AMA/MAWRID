import { createContext, useContext, useState, useCallback, ReactNode } from "react";

export type SchemaSource = "default" | "custom";

interface SchemaContextValue {
  source: SchemaSource;
  customToken: string;
  customName: string;
  setCustomSchema: (token: string, name: string) => void;
  clearCustomSchema: () => void;
}

const SchemaContext = createContext<SchemaContextValue | null>(null);

export function SchemaProvider({ children }: { children: ReactNode }) {
  const [customToken, setCustomToken] = useState("");
  const [customName, setCustomName] = useState("");

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
    <SchemaContext.Provider value={{ source, customToken, customName, setCustomSchema, clearCustomSchema }}>
      {children}
    </SchemaContext.Provider>
  );
}

export function useSchemaCtx() {
  const ctx = useContext(SchemaContext);
  if (!ctx) throw new Error("useSchemaCtx must be used inside SchemaProvider");
  return ctx;
}
