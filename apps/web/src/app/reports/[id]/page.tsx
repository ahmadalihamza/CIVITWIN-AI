import { PlanningReport } from "@/components/results/planning-report";

export default async function ReportPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <PlanningReport runId={id} />;
}
