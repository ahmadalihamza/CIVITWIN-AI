import { RunMonitor } from "@/components/planning/run-monitor";

export default async function Page({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ baseline?: string }>;
}) {
  const [{ id }, { baseline }] = await Promise.all([params, searchParams]);
  return <RunMonitor key={id} runId={id} baselineId={baseline} />;
}
