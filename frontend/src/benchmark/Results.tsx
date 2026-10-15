import React, { useState, useEffect } from "react";
import { type Run, type Scenario } from "./domain";
import { Empty, Tabs } from "./shared";
import RunDetails from "./RunDetails";
import ResearchResults from "./ResearchResults";
import { officialResults } from "./analysis";

export default function Results({
  runs,
  scenarios,
  runId,
  onRun,
  onBack,
  onStart,
}: {
  runs: Run[];
  scenarios: Scenario[];
  runId?: string;
  onRun: (id: string) => void;
  onBack: () => void;
  onStart: () => void;
}) {
  const [view, setView] = useState("Summary"),
    [data, setData] = useState<any>(null),
    [error, setError] = useState("");
  useEffect(() => {
    let live = true;
    officialResults()
      .then((d) => {
        if (live) {
          setData(d);
          setError("");
        }
      })
      .catch((e) => {
        if (live) setError(e.message);
      });
    return () => {
      live = false;
    };
  }, [runs]);
  if (error) return <Empty title="Results unavailable">{error}</Empty>;
  if (!data) return <Empty title="Loading benchmark results…" />;
  if (runId) {
    const run = data.runs.find((r: Run) => r.id === runId);
    return (
      <>
        <div className="toolbar">
          <button onClick={onBack}>← Results</button>
        </div>
        {run ? (
          <RunDetails
            run={run}
            scenario={scenarios.find((s) => s.id === run.scenario)}
          />
        ) : (
          <Empty title="Run is not in the official evaluation dataset">
            Internal validation and incompatible experiments remain separate.
          </Empty>
        )}
      </>
    );
  }
  return (
    <>
      <Tabs
        label="Results views"
        items={[
          "Summary",
          "Model Comparison",
          "Scenario Analysis",
          "Payment & Stage Analysis",
          "Run Explorer",
        ]}
        value={view}
        onChange={setView}
      />
      <ResearchResults
        view={view}
        onRun={onRun}
        onStart={onStart}
        data={data}
      />
    </>
  );
}
