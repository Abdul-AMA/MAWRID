import ExperimentLog from "@/components/ExperimentLog";

interface Props { dir: "rtl" | "ltr" }

export default function ExperimentsPage({ dir }: Props) {
  return (
    <div className="max-w-7xl mx-auto px-4 py-8 space-y-6">
      <div>
        <h1 className="text-2xl font-bold">
          {dir === "rtl" ? "لوحة التجارب" : "Experiments Dashboard"}
        </h1>
        <p className="text-muted-foreground text-sm mt-1">
          {dir === "rtl"
            ? "سجل جميع عمليات المعالجة مع مقاييس الأداء والتكلفة"
            : "All pipeline runs with accuracy, cost, and latency metrics"}
        </p>
      </div>

      <ExperimentLog dir={dir} />
    </div>
  );
}
