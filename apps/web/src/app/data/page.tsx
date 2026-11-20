"use client";

import Link from "next/link";
import { type FormEvent, useState } from "react";
import { Loading, useData } from "@/components/load";
import { Network } from "@/components/network";
import { api, ApiError, errorMessage, formatDate, formatNumber } from "@/lib/api";
import type { Dataset, DatasetManifest } from "@/lib/types";

export default function DataExplorer() {
  const [selected, setSelected] = useState("demo-bajaur-v1");
  const [importing, setImporting] = useState(false);
  const [notice, setNotice] = useState<{ message: string; error?: boolean }>();
  const catalog = useData<DatasetManifest[]>("/datasets");
  const { data, error, retry } = useData<Dataset>("/datasets/" + encodeURIComponent(selected));

  async function importVersion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (importing) return;
    const form = event.currentTarget;
    const file = new FormData(form).get("bundle");
    if (!(file instanceof File) || !file.size || file.size > 2_000_000) {
      setNotice({ message: "Select a JSON dataset or CSV bundle up to 2 MB.", error: true });
      return;
    }
    setImporting(true);
    setNotice(undefined);
    try {
      const uploaded = await api<DatasetManifest>("/datasets/import", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: file,
      });
      form.reset();
      setSelected(uploaded.id);
      catalog.retry();
      setNotice({ message: "Published synthetic version " + uploaded.id + "." });
    } catch (failure) {
      const details = failure instanceof ApiError
        ? failure.fields.slice(0, 4).map((item) => item.field.join(".") + " · " + item.message)
        : [];
      setNotice({ message: [errorMessage(failure), ...details].join(" "), error: true });
    } finally {
      setImporting(false);
    }
  }

  return <div className="stack">
    <section className="page-heading"><div><div className="eyebrow">Inputs and provenance</div>
      <h1>Explore the Bajaur dataset</h1>
      <p className="muted">Inspect the modeled demand, capacity, and travel assumptions shared by both allocations.</p>
    </div><Link className="button primary" href={"/scenarios/new?dataset=" + encodeURIComponent(selected)}>Start scenario</Link></section>
    <section className="panel side-panel">
      {catalog.data && <label className="layer-control">Dataset version <select value={selected}
        onChange={(event) => setSelected(event.target.value)}>
        {catalog.data.map((item) => <option key={item.id} value={item.id}>{item.id} · {item.version}</option>)}
      </select></label>}
      <details><summary>Import a synthetic dataset</summary>
        <form className="import-form" onSubmit={importVersion}>
          <label>Dataset or JSON-wrapped CSV bundle <input name="bundle" type="file" accept=".json,application/json" required /></label>
          <button className="button" type="submit" disabled={importing}>{importing ? "Checking bundle…" : "Publish version"}</button>
        </form>
        {notice && <p role={notice.error ? "alert" : "status"} className={notice.error ? "notice" : "muted"}>{notice.message}</p>}
      </details>
    </section>
    {data ? <>
      <div className="overview-grid"><Network dataset={data} />
        <section className="panel side-panel"><h2>Dataset manifest</h2>
          <dl className="scope-list">
            <div><dt>Dataset</dt><dd>{data.id} · {data.version}</dd></div>
            <div><dt>Type</dt><dd>{data.is_synthetic ? "Synthetic" : "Aggregate"}</dd></div>
            <div><dt>Source date</dt><dd>{formatDate(data.source_date)}</dd></div>
            <div><dt>License</dt><dd>{data.license}</dd></div>
            <div><dt>Reachable pairs</dt><dd>{data.reachable_pair_count}</dd></div>
            <div><dt>Unreachable pairs</dt><dd>{data.unreachable_pair_count}</dd></div>
          </dl>
          <h3>SHA-256</h3><code className="hash">{data.sha256}</code>
          <p className="muted">{data.model_scope}</p>
        </section>
      </div>
      <div className="data-grid">
        <section className="panel side-panel"><h2>Community demand</h2><div className="table-wrap" tabIndex={0}>
          <table><caption className="sr-only">Community demand per modeled week</caption><thead><tr>
            <th scope="col">Cluster</th><th scope="col">Zone class</th><th scope="col">Visits/week</th>
          </tr></thead><tbody>{data.communities.map((row) => <tr key={row.id}>
            <th scope="row">{row.id}</th><td>{row.zone_class}</td><td>{formatNumber(row.demand_visits_per_week)}</td>
          </tr>)}</tbody></table>
        </div></section>
        <section className="panel side-panel"><h2>Service capacity</h2><div className="table-wrap" tabIndex={0}>
          <table><caption className="sr-only">Site capacity and candidate eligibility</caption><thead><tr>
            <th scope="col">Site</th><th scope="col">Type</th><th scope="col">Visits/week</th><th scope="col">PKR/week</th>
          </tr></thead><tbody>{data.sites.map((row) => <tr key={row.id}>
            <th scope="row">{row.id}</th><td>{row.type}{row.type === "candidate" && !row.eligible ? " (ineligible)" : ""}</td>
            <td>{formatNumber(row.capacity_per_week)}</td><td>{formatNumber(row.fixed_cost_pkr)}</td>
          </tr>)}</tbody></table>
        </div></section>
      </div>
      <section className="panel side-panel"><h2>Assumptions and provenance</h2>
        <ul className="text-list">{data.assumptions.map((value) => <li key={value}>{value}</li>)}</ul>
        {data.unreachable_pair_count > 0 && <p className="notice">Unreachable pairs are excluded from assignment.</p>}
        <div className="table-wrap" tabIndex={0}><table><caption className="sr-only">Dataset provenance</caption>
          <thead><tr><th scope="col">Entity and field</th><th scope="col">Source</th><th scope="col">Method</th><th scope="col">Caveat</th></tr></thead>
          <tbody>{data.provenance.map((item, index) => <tr key={index}><th scope="row">{item.entity} · {item.field}</th>
            <td>{item.source}</td><td>{item.method}</td><td>{item.caveat}</td></tr>)}</tbody>
        </table></div>
      </section>
    </> : <Loading error={error} retry={retry} />}
  </div>;
}
