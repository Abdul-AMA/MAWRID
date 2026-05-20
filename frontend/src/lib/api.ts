import axios from "axios";

export const api = axios.create({
  baseURL: "/api",
  timeout: 30_000,
});

// ── Types (mirror backend schemas) ───────────────────────────────────────────

export type JobStatus = "pending" | "running" | "completed" | "failed";

export interface ExtractedField {
  field_id: string;
  value: string | null;
  confidence: number;
  low_confidence: boolean;
}

export interface StageResult {
  name: string;
  status: "waiting" | "running" | "done" | "failed";
  latency_ms: number | null;
  output_summary: string | null;
}

export interface PipelineResult {
  doc_type: string;
  combo: string;
  stages: StageResult[];
  fields: ExtractedField[];
  confidence_avg: number;
  estimated_cost_usd: number;
  total_latency_ms: number;
  mlflow_run_id: string | null;
}

export interface JobResponse {
  job_id: string;
  status: JobStatus;
  combo: string;
  filename: string;
  result: PipelineResult | null;
  error: string | null;
}

export interface ComboInfo {
  name: string;
  description: string;
  ocr: string;
  classifier: string;
  extractor: string;
  sends_images_to_cloud: boolean;
  active: boolean;
}

export interface ComboListResponse {
  combos: ComboInfo[];
  active: string;
}

export interface ExperimentRun {
  run_id: string;
  combo: string;
  doc_type: string;
  num_fields: number;
  fields_matched: number;
  precision: number;
  recall: number;
  confidence_avg: number;
  estimated_cost_usd: number;
  latency_ms: number;
  timestamp: string;
  azure_di_model_id: string | null;
  azure_pages_billed: number | null;
  azure_confidence: number | null;
}

export interface ExperimentsResponse {
  runs: ExperimentRun[];
  total: number;
}

// ── API helpers ───────────────────────────────────────────────────────────────

export const uploadDocument = (file: File) => {
  const form = new FormData();
  form.append("file", file);
  return api.post<{ job_id: string; status: string; message: string }>(
    "/documents/upload",
    form,
    { headers: { "Content-Type": "multipart/form-data" } }
  );
};

export const getJob = (jobId: string) =>
  api.get<JobResponse>(`/documents/${jobId}`);

export const getCombos = () => api.get<ComboListResponse>("/combos");

export const setCombo = (combo: string) =>
  api.post<{ active: string; message: string }>("/combos/set", { combo });

export const getExperiments = (limit = 100, offset = 0) =>
  api.get<ExperimentsResponse>(`/experiments?limit=${limit}&offset=${offset}`);

export const compareExperiments = (run_id_a: string, run_id_b: string) =>
  api.post("/experiments/compare", { run_id_a, run_id_b });

// ── Schema ────────────────────────────────────────────────────────────────────

export interface SchemaField {
  id: string;
  label_ar: string;
  type: "text" | "date" | "number" | "lookup" | "var" | string;
  required: boolean;
  options?: string[];
}

export interface SchemaDocument {
  label_ar: string;
  category: string;
  category_label_ar: string;
  fields: SchemaField[];
}

export interface SchemaResponse {
  _meta: Record<string, unknown>;
  _categories: Record<string, { label_ar: string }>;
  documents: Record<string, SchemaDocument>;
}

export const getSchema = () => api.get<SchemaResponse>("/schema");

// ── Saved documents ───────────────────────────────────────────────────────────

export interface SavedFieldRecord {
  field_id: string;
  label_ar: string;
  value: string | null;
  confidence: number;
}

export interface SavedDocumentRecord {
  id: string;
  filename: string;
  category: string;
  category_label: string;
  doc_type: string;
  doc_type_label: string;
  combo: string;
  confidence: number;
  cost: number;
  latency: number;
  created_at: string;
  fields: SavedFieldRecord[];
}

export interface SaveDocumentPayload {
  file: File;
  category: string;
  categoryLabel: string;
  docType: string;
  docTypeLabel: string;
  combo: string;
  confidence: number;
  cost: number;
  latency: number;
  fields: SavedFieldRecord[];
}

export const saveDocument = (payload: SaveDocumentPayload) => {
  const form = new FormData();
  form.append("file",           payload.file);
  form.append("category",       payload.category);
  form.append("category_label", payload.categoryLabel);
  form.append("doc_type",       payload.docType);
  form.append("doc_type_label", payload.docTypeLabel);
  form.append("combo",          payload.combo);
  form.append("confidence",     String(payload.confidence));
  form.append("cost",           String(payload.cost));
  form.append("latency",        String(payload.latency));
  form.append("fields_json",    JSON.stringify(payload.fields));
  return api.post<SavedDocumentRecord>("/saved", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
};

export const getSavedDocuments = (limit = 100, offset = 0) =>
  api.get<{ records: SavedDocumentRecord[]; total: number }>(
    `/saved?limit=${limit}&offset=${offset}`
  );

export const deleteSavedDocument = (id: string) =>
  api.delete(`/saved/${id}`);

// ── OCR Stage ─────────────────────────────────────────────────────────────────

export interface OcrDetection {
  text: string;
  confidence: number;
  bbox: [number, number][];   // [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]
  page: number;
  index: number;
}

export interface OcrPage {
  image_b64: string;          // JPEG base64
  width: number;
  height: number;
  detections: OcrDetection[];
}

export interface OcrResult {
  text: string;
  backend: string;
  latency_ms: number;
  pages: OcrPage[];
}

export const LOCAL_OCR_BACKENDS = ["paddleocr", "easyocr"] as const;
export type LocalOcrBackend = (typeof LOCAL_OCR_BACKENDS)[number];

// ── Vision OCR (Anthropic) ────────────────────────────────────────────────────

export interface VisionOcrResult {
  text: string;
  model: string;
  latency_ms: number;
  page_images: string[];   // base64 JPEGs, one per page
  input_tokens: number;
  output_tokens: number;
}

export const getVisionModels = () =>
  api.get<{ models: string[] }>("/ocr/vision/models");

export const runVisionOcr = (file: File, model: string, prompt: string) => {
  const form = new FormData();
  form.append("file", file);
  form.append("model", model);
  form.append("prompt", prompt);
  return api.post<VisionOcrResult>("/ocr/vision", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
};

// ── Gemini Vision OCR ─────────────────────────────────────────────────────────

export const getGeminiModels = () =>
  api.get<{ models: string[] }>("/ocr/gemini/models");

export const runGeminiOcr = (file: File, model: string, prompt: string) => {
  const form = new FormData();
  form.append("file", file);
  form.append("model", model);
  form.append("prompt", prompt);
  return api.post<VisionOcrResult>("/ocr/gemini", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
};

export const getOcrConfig = () =>
  api.get<{ paddleocr: Record<string, unknown> }>("/ocr/config");

// ── Azure Document Intelligence OCR ──────────────────────────────────────────

export interface AzureOcrResult {
  text: string;
  model: string;
  latency_ms: number;
  page_images: string[];
  pages_billed: number;
}

export const getAzureModels = () =>
  api.get<{ models: string[] }>("/ocr/azure/models");

export const runAzureOcr = (file: File, model: string) => {
  const form = new FormData();
  form.append("file", file);
  form.append("model", model);
  return api.post<AzureOcrResult>("/ocr/azure", form, {
    headers: { "Content-Type": "multipart/form-data" },
    timeout: 120_000,
  });
};

// ── Groq Vision OCR ───────────────────────────────────────────────────────────

export const getGroqModels = () =>
  api.get<{ models: string[] }>("/ocr/groq/models");

export const runGroqOcr = (file: File, model: string, prompt: string) => {
  const form = new FormData();
  form.append("file", file);
  form.append("model", model);
  form.append("prompt", prompt);
  return api.post<VisionOcrResult>("/ocr/groq", form, {
    headers: { "Content-Type": "multipart/form-data" },
    timeout: 120_000,
  });
};

// ── OpenRouter Vision OCR ─────────────────────────────────────────────────────

export const getOpenRouterModels = () =>
  api.get<{ models: string[] }>("/ocr/openrouter/models");

export const runOpenRouterOcr = (file: File, model: string, prompt: string) => {
  const form = new FormData();
  form.append("file", file);
  form.append("model", model);
  form.append("prompt", prompt);
  return api.post<VisionOcrResult>("/ocr/openrouter", form, {
    headers: { "Content-Type": "multipart/form-data" },
    timeout: 120_000,
  });
};

export const runOcr = (
  file: File,
  backend: LocalOcrBackend,
  params?: Record<string, unknown>,
) => {
  const form = new FormData();
  form.append("file", file);
  form.append("backend", backend);
  if (params) form.append("params_json", JSON.stringify(params));
  return api.post<OcrResult>("/ocr/run", form, {
    headers: { "Content-Type": "multipart/form-data" },
    timeout: 600_000,
  });
};

// ── Two-Stage Pipeline ────────────────────────────────────────────────────────

export interface ThreeStageStage1 {
  raw_text:      string;
  page_images:   string[];
  model:         string;
  latency_ms:    number;
  input_tokens:  number;
  output_tokens: number;
}

export interface ThreeStageStage2 {
  document_type:       string;
  document_type_label: string;
  confidence:          "high" | "medium" | "low";
  field_count:         number;
  model:               string;
  latency_ms:          number;
  input_tokens:        number;
  output_tokens:       number;
}

export interface ThreeStageStage3 {
  fields:        Record<string, string | number | null>;
  model:         string;
  latency_ms:    number;
  input_tokens:  number;
  output_tokens: number;
}

export interface ThreeStageResult {
  stage1: ThreeStageStage1;
  stage2: ThreeStageStage2;
  stage3: ThreeStageStage3;
}

export const getTwoStageModels = () =>
  api.get<{ stage1: string[]; stage2: string[]; stage3: string[] }>("/two-stage/models");

export const runTwoStage = (
  file: File,
  stage1_backend: string,
  stage2_backend: string,
  stage3_backend: string,
) => {
  const form = new FormData();
  form.append("file",           file);
  form.append("stage1_backend", stage1_backend);
  form.append("stage2_backend", stage2_backend);
  form.append("stage3_backend", stage3_backend);
  return api.post<ThreeStageResult>("/two-stage/run", form, {
    headers: { "Content-Type": "multipart/form-data" },
    timeout: 180_000,
  });
};

// Derived UI types built from the schema
export interface UIField {
  id: string;
  labelAr: string;
  type: string;
  required: boolean;
  options?: string[];
}

export interface UIDocType {
  id: string;
  labelAr: string;
  fields: UIField[];
}

export interface UICategory {
  id: string;
  labelAr: string;
  types: UIDocType[];
}

export function buildUICategories(schema: SchemaResponse): UICategory[] {
  const grouped: Record<string, UIDocType[]> = {};

  for (const [docId, doc] of Object.entries(schema.documents)) {
    if (!grouped[doc.category]) grouped[doc.category] = [];
    grouped[doc.category].push({
      id: docId,
      labelAr: doc.label_ar,
      fields: doc.fields.map((f) => ({
        id: f.id,
        labelAr: f.label_ar,
        type: f.type,
        required: f.required,
        options: (f as any).options,
      })),
    });
  }

  // _categories may be absent from older schema files — fall back to deriving from documents
  if (schema._categories) {
    return Object.entries(schema._categories).map(([catId, catInfo]) => ({
      id: catId,
      labelAr: catInfo.label_ar,
      types: grouped[catId] ?? [],
    }));
  }

  return Object.keys(grouped).map(catId => ({
    id: catId,
    labelAr: catId,
    types: grouped[catId],
  }));
}
