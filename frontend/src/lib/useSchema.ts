import { useQuery } from "@tanstack/react-query";
import { getSchema, SchemaResponse } from "./api";
import { useSchemaCtx } from "./schemaContext";

export function useSchema() {
  const { source, customToken } = useSchemaCtx();

  return useQuery<SchemaResponse>({
    queryKey: ["schema", source === "custom" ? customToken : "default"],
    queryFn: async () => {
      const opts = source === "custom" ? { token: customToken } : {};
      return (await getSchema(opts)).data;
    },
    staleTime: Infinity,
    retry: false,
  });
}
