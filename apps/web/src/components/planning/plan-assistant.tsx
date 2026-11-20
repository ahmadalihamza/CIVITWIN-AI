"use client";

import { type FormEvent, useEffect, useRef, useState } from "react";
import { api, errorMessage } from "@/lib/api";
import type { PlanSpec } from "@/lib/types";
import { PlanAssumptions } from "./assumptions";
import styles from "./planning.module.css";

type PromptLanguage = "en" | "ur" | "ps";

type ParseResponse = {
  status: "draft" | "clarification" | "manual";
  draft: PlanSpec | null;
  warnings: string[];
  defaults_applied: string[];
};

const labels: Record<string, string> = {
  budget_pkr: "Budget",
  max_new_units: "Maximum new units",
  threshold_minutes: "Coverage threshold",
  demand_multiplier_pct: "Demand multiplier",
  equity_min_pct: "Equity floor",
  policy: "Allocation policy",
  seed: "Solver seed",
};

export function PlanAssistant({ datasetId, disabled, onApply }: {
  datasetId: string;
  disabled: boolean;
  onApply: (plan: PlanSpec) => void;
}) {
  const [language, setLanguage] = useState<PromptLanguage>("en");
  const [prompt, setPrompt] = useState("");
  const [suggestion, setSuggestion] = useState<ParseResponse>();
  const [applied, setApplied] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const requestRef = useRef<AbortController | null>(null);

  useEffect(() => () => requestRef.current?.abort(), []);

  function clearSuggestion() {
    setSuggestion(undefined);
    setApplied(false);
    setError("");
  }

  async function suggest(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (disabled || requestRef.current || !prompt.trim()) return;
    clearSuggestion();
    setBusy(true);
    const controller = new AbortController();
    requestRef.current = controller;
    try {
      const result = await api<ParseResponse>("/plans/parse", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ dataset_version_id: datasetId, text: prompt.trim(), language }),
        signal: controller.signal,
      });
      if (controller.signal.aborted) return;
      if (result.draft && result.draft.dataset_version_id !== datasetId) {
        setError("The suggestion used a different dataset.");
        return;
      }
      setSuggestion(result);
    } catch (problem) {
      if (!controller.signal.aborted) setError(errorMessage(problem));
    } finally {
      requestRef.current = null;
      if (!controller.signal.aborted) setBusy(false);
    }
  }

  const draft = suggestion?.status === "draft" ? suggestion.draft : null;

  return (
    <section className={styles.assistant} aria-labelledby="plan-assistant-heading">
      <h2 id="plan-assistant-heading">Draft with AI</h2>
      <p className="muted">Use synthetic planning details. Your prompt goes to the configured AI provider.</p>
      <form className={styles.assistant} onSubmit={suggest}>
        <div className={styles.field}>
          <label htmlFor="prompt-language">Prompt language</label>
          <select id="prompt-language" value={language} disabled={disabled || busy} onChange={(event) => {
            setLanguage(event.target.value as PromptLanguage);
            clearSuggestion();
          }}>
            <option value="en">English</option>
            <option value="ur">Urdu</option>
            <option value="ps">Pashto</option>
          </select>
        </div>
        <div className={styles.field}>
          <label htmlFor="planning-prompt">Planning prompt</label>
          <textarea id="planning-prompt" rows={4} maxLength={500} disabled={disabled || busy}
            lang={language} dir={language === "en" ? "ltr" : "rtl"} value={prompt}
            aria-describedby="planning-prompt-help"
            onChange={(event) => { setPrompt(event.target.value); clearSuggestion(); }} />
          <small id="planning-prompt-help" className="muted">Describe the weekly budget, unit limit, or coverage threshold. Up to 500 characters.</small>
        </div>
        <button className="button" type="submit" disabled={disabled || busy || !prompt.trim()}>
          {busy ? "Requesting a suggestion…" : "Suggest plan"}
        </button>
      </form>
      {busy && <p className="muted" role="status">Waiting for the AI provider.</p>}
      {error && <div className="notice" role="alert"><p>{error}</p><p>Continue with the manual form.</p></div>}
      {suggestion && (
        <div className={styles.assistant + " notice"}>
          <h3 aria-live="polite">{draft ? "Suggested assumptions" : suggestion.status === "clarification" ? "More detail needed" : "Manual planning available"}</h3>
          {suggestion.warnings.map((warning, index) => <p key={index}>{warning}</p>)}
          {draft ? (
            <>
              {suggestion.defaults_applied.length > 0 && (
                <p><strong>Defaults used</strong>{" · "}{suggestion.defaults_applied.map((field) => labels[field] ?? field).join(", ")}</p>
              )}
              <PlanAssumptions plan={draft} />
              <button className="button" type="button" disabled={disabled || applied} onClick={() => {
                onApply(draft);
                setApplied(true);
              }}>{applied ? "Suggestion applied" : "Apply suggestion"}</button>
            </>
          ) : <p>Revise your prompt or continue with the manual form.</p>}
        </div>
      )}
    </section>
  );
}
