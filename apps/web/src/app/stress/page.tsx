import { StressLab } from "@/components/stress/stress-lab";

type Query = Record<"baseline" | "alternative" | "run", string | string[] | undefined>;

export default async function StressPage({ searchParams }: { searchParams: Promise<Query> }) {
  const query = await searchParams;
  const text = (name: keyof Query) => typeof query[name] === "string" ? query[name] : undefined;
  const baselineId = text("baseline");
  const alternativeId = text("alternative");
  const stressId = text("run");
  return <StressLab key={JSON.stringify([stressId, baselineId, alternativeId])}
    baselineId={baselineId} alternativeId={alternativeId} stressId={stressId} />;
}
