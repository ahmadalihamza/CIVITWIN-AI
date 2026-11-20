import { ComparisonView } from "@/components/results/comparison-view";

type Search = { baseline?: string | string[]; alternative?: string | string[] };

export default async function ComparePage({ searchParams }: { searchParams: Promise<Search> }) {
  const { baseline, alternative } = await searchParams;
  return (
    <ComparisonView
      baselineId={typeof baseline === "string" ? baseline : undefined}
      alternativeId={typeof alternative === "string" ? alternative : undefined}
    />
  );
}
