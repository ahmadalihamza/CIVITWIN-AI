"use client";

import Link from "next/link";
import { Icon, type IconName } from "@/components/icon";
import { Loading, useData } from "@/components/load";
import { Network } from "@/components/network";
import { formatDate, formatNumber } from "@/lib/api";
import type { Dataset, RunSnapshot } from "@/lib/types";

export default function Overview() {
  const dataset = useData<Dataset>("/datasets/demo-bajaur-v1");
  const history = useData<RunSnapshot[]>("/runs");
  const record = dataset.data;
  const stats: { label: string; value: number; unit: string; icon: IconName }[] = record ? [
    { label: "Community clusters", value: record.communities.length, unit: "Schematic demand zones", icon: "grid" },
    { label: "Weekly demand", value: record.communities.reduce((sum, row) => sum + row.demand_visits_per_week, 0), unit: "Requested visits", icon: "activity" },
    { label: "Existing sites", value: record.sites.filter((row) => row.type === "existing").length, unit: "Available in the baseline", icon: "site" },
    { label: "Candidate zones", value: record.sites.filter((row) => row.type === "candidate" && row.eligible).length, unit: "Eligible planning options", icon: "pin" },
  ] : [];

  return <div className="stack">
    <section className="page-heading overview-heading">
      <div><div className="eyebrow">Outpatient accessibility</div><h1>Bajaur planning overview</h1>
        <p className="muted">Model weekly service access, test an allocation, and inspect the evidence behind every result.</p></div>
      <Link className="button primary overview-cta" href="/scenarios/new">Start scenario <Icon name="arrow" /></Link>
    </section>
    <section className="panel" style={{ display: "flex", gap: 18, alignItems: "center", justifyContent: "space-between", padding: "20px 24px", background: "linear-gradient(110deg, #e8f7ea, #fff)" }}>
      <div style={{ display: "grid", gap: 5 }}>
        <div className="eyebrow">NEW · Interactive decision lab</div>
        <h2>Who gets care next?</h2>
        <p className="muted" style={{ maxWidth: "58ch", fontSize: ".83rem" }}>Choose a public health challenge, adjust your budget, run the real planning engine and see which communities gain or lose modeled access.</p>
      </div>
      <Link className="button primary" href="/studio">Explore Impact Studio <Icon name="arrow" /></Link>
    </section>
    {record ? <>
      <div className="stats-grid">
        {stats.map((stat) => <div className="panel stat-card" key={stat.label}>
          <span className="stat-icon"><Icon name={stat.icon} /></span><div>
            <div className="stat-title">{stat.label}</div><strong>{formatNumber(stat.value)}</strong><div className="muted">{stat.unit}</div>
          </div>
        </div>)}
      </div>
      <div className="overview-grid">
        <Network dataset={record} />
        <div className="stack overview-aside">
          <section className="panel side-panel">
            <div className="section-head"><h2>Recent runs</h2><Icon name="clock" /></div>
            {history.data ? history.data.length ?
              <ul className="run-list">{history.data.slice(0, 4).map((run) =>
                <li key={run.run_id}><Link href={"/runs/" + run.run_id}>
                  <span><b>{run.kind === "baseline" ? "Modeled baseline" : run.kind === "optimized" ? "Optimized plan" : "Greedy benchmark"}</b>
                    <small>{formatDate(run.created_at)}</small></span>
                  <span className="badge">{run.status.replaceAll("_", " ").toLowerCase()}</span></Link></li>)}</ul> :
              <p className="muted">Your saved planning runs will appear here after you confirm a scenario.</p> :
              <Loading error={history.error} retry={history.retry} />}
          </section>
          <section className="panel side-panel">
            <div className="section-head"><h2>Dataset and scope</h2><Icon name="database" /></div>
            <dl className="scope-list">
              <div><dt>Dataset</dt><dd>{record.id}</dd></div>
              <div><dt>Version</dt><dd>{record.version}</dd></div>
              <div><dt>Source date</dt><dd>{formatDate(record.source_date)}</dd></div>
              <div><dt>Time horizon</dt><dd>One modeled week</dd></div>
            </dl>
            <Link href="/data" className="panel-link">Inspect dataset <Icon name="arrow" /></Link>
          </section>
        </div>
      </div>
    </> : <Loading error={dataset.error} retry={dataset.retry} />}
  </div>;
}
