import AssistPage from "./AssistPage";

interface Props { dir: "rtl" | "ltr" }

const CLAUDE_HAIKU  = "claude/claude-haiku-4-5-20251001";
const CLAUDE_SONNET = "claude/claude-sonnet-4-6";

export default function AssistClaudeHaikuPage({ dir }: Props) {
  return (
    <AssistPage
      dir={dir}
      promptLang="en"
      stage1ModelOverride={CLAUDE_HAIKU}
      modelOverride={CLAUDE_SONNET}
    />
  );
}
