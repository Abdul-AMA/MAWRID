import AssistPage from "./AssistPage";

interface Props { dir: "rtl" | "ltr" }

const CLAUDE_SONNET = "claude/claude-sonnet-4-6";

export default function AssistClaudePage({ dir }: Props) {
  return <AssistPage dir={dir} promptLang="en" modelOverride={CLAUDE_SONNET} />;
}
