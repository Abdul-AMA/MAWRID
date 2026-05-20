import AssistPage from "./AssistPage";

interface Props { dir: "rtl" | "ltr" }

export default function OllamaAssistPage({ dir }: Props) {
  return (
    <AssistPage
      dir={dir}
      defaultModel="ollama/qwen2.5vl:3b"
      providerPrefix="ollama/"
    />
  );
}
