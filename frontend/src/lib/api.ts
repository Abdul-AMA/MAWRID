import axios from "axios";

export const api = axios.create({
  baseURL: "/api",
  timeout: 30_000,
});

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

// ── Three-Stage Pipeline ──────────────────────────────────────────────────────

export interface ThreeStageStage1 {
  raw_text:      string;
  page_images:   string[];
  model:         string;
  latency_ms:    number;
  input_tokens:  number;
  output_tokens: number;
  prompt?:       string;
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
  prompt?:             string;
}

export interface ThreeStageStage3 {
  fields:        Record<string, string | number | null>;
  model:         string;
  latency_ms:    number;
  input_tokens:  number;
  output_tokens: number;
  prompt?:       string;
}

export interface ThreeStageResult {
  stage1: ThreeStageStage1;
  stage2: ThreeStageStage2;
  stage3: ThreeStageStage3;
}

export const runTwoStage = (
  file: File,
  stage1_backend: string,
  stage2_backend: string,
  stage3_backend: string,
  promptLang: "ar" | "en" | "en-ocr" = "ar",
) => {
  const form = new FormData();
  form.append("file",           file);
  form.append("stage1_backend", stage1_backend);
  form.append("stage2_backend", stage2_backend);
  form.append("stage3_backend", stage3_backend);
  form.append("prompt_lang",    promptLang);
  return api.post<ThreeStageResult>("/two-stage/run", form, {
    headers: { "Content-Type": "multipart/form-data" },
    timeout: 180_000,
  });
};

// ── Derived UI types built from the schema ────────────────────────────────────

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
