import AssistPage from "./AssistPage";

interface Props { dir: "rtl" | "ltr" }

export default function ClaudeAssistPage({ dir }: Props) {
  return (
    <AssistPage
      dir={dir}
      defaultModel="claude/claude-sonnet-4-6"
      providerPrefix="claude/"
    />
  );
}
