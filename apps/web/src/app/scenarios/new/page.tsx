import { ScenarioBuilder } from "@/components/planning/scenario-builder";

export default async function Page({
  searchParams,
}: {
  searchParams: Promise<{ dataset?: string; draft?: string }>;
}) {
  const { dataset, draft } = await searchParams;
  return <ScenarioBuilder key={draft ?? dataset} draftId={draft} datasetId={dataset} />;
}
