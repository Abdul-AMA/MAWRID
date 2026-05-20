import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getCombos, setCombo, ComboInfo } from "@/lib/api";
import { cn } from "@/lib/utils";
import { AlertTriangle, CheckCircle2 } from "lucide-react";

interface Props {
  dir: "rtl" | "ltr";
}

export default function ComboSelector({ dir }: Props) {
  const qc = useQueryClient();
  const { data } = useQuery({
    queryKey: ["combos"],
    queryFn: () => getCombos().then((r) => r.data),
  });

  const mutation = useMutation({
    mutationFn: (combo: string) => setCombo(combo),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["combos"] }),
  });

  if (!data) return null;

  return (
    <div className="space-y-2">
      <label className="text-sm font-medium text-muted-foreground">
        {dir === "rtl" ? "التركيبة النشطة" : "Active Combo"}
      </label>
      <div className="grid gap-2">
        {data.combos.map((c: ComboInfo) => (
          <button
            key={c.name}
            onClick={() => mutation.mutate(c.name)}
            disabled={mutation.isPending}
            className={cn(
              "w-full text-start p-3 rounded-lg border text-sm transition-all",
              c.active
                ? "border-primary bg-primary/5 shadow-sm"
                : "border-border hover:border-primary/40 hover:bg-muted/50"
            )}
          >
            <div className="flex items-center justify-between gap-2 mb-1">
              <span className="font-mono font-semibold text-xs tracking-wider">
                {c.name}
              </span>
              <div className="flex items-center gap-1.5">
                {c.sends_images_to_cloud && (
                  <span
                    title={
                      dir === "rtl"
                        ? "يرسل صور إلى السحابة"
                        : "Sends images to cloud"
                    }
                    className="text-amber-500"
                  >
                    <AlertTriangle className="w-3.5 h-3.5" />
                  </span>
                )}
                {c.active && (
                  <CheckCircle2 className="w-3.5 h-3.5 text-primary" />
                )}
              </div>
            </div>
            <p className="text-xs text-muted-foreground leading-relaxed">
              {c.description}
            </p>
          </button>
        ))}
      </div>
    </div>
  );
}
