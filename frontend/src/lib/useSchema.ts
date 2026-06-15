import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { getSchema, SchemaResponse } from "./api";
import { useSchemaCtx } from "./schemaContext";

export function useSchema() {
  const ctx = useSchemaCtx();
  const qc = useQueryClient();
  const [needsPassword, setNeedsPassword] = useState(false);

  const { source, customToken, password } = ctx;

  const query = useQuery<SchemaResponse>({
    queryKey: ["schema", source === "custom" ? customToken : password],
    queryFn: async () => {
      try {
        const opts = source === "custom"
          ? { token: customToken }
          : { password: password || undefined };
        return (await getSchema(opts)).data;
      } catch (err: any) {
        if (err?.response?.status === 401) {
          setNeedsPassword(true);
        }
        throw err;
      }
    },
    staleTime: Infinity,
    retry: false,
  });

  const handlePasswordSubmit = (pwd: string) => {
    ctx.setPassword(pwd);
    setNeedsPassword(false);
    qc.invalidateQueries({ queryKey: ["schema"] });
  };

  return { ...query, needsPassword, handlePasswordSubmit };
}
