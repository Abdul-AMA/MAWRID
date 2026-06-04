import AssistPage from "./AssistPage";

interface Props { dir: "rtl" | "ltr" }

export default function AssistEnPage({ dir }: Props) {
  return <AssistPage dir={dir} promptLang="en" />;
}
