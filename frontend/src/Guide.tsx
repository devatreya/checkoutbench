import React from "react";

export const sectionHelp: Record<string, { purpose: string; next: string }> = {
  Overview: {
    purpose:
      "Start here: check the benchmark software or prepare an AI evaluation.",
    next: "A software check uses programmed rules and makes no model inference calls.",
  },
  Models: {
    purpose:
      "Step 1 · Choose who makes the decisions: a reference script or an actual AI system.",
    next: "Ready means the system can be selected. Configured means its setup still needs a real inference check. Unavailable explains what is missing.",
  },
  Scenarios: {
    purpose:
      "Step 2 · Choose the checkout tasks, repetitions and limits, then review and start your batch.",
    next: "The preview is a separate practice session. Every scored trial starts fresh with the selected customer, seed and device.",
  },
  Coverage: {
    purpose:
      "Inspect what each scenario tests, its source references, and which behavior is synthetic.",
    next: "Try a checkout manually or validate one reference path. Author-only criteria shown here are kept outside the agent browser.",
  },
  "Live session": {
    purpose:
      "Watch the active batch: browser screenshots, actions, progress and spending.",
    next: "Pause takes effect at an action boundary. Stop cancels the current run and the remaining queue; recorded results stay saved.",
  },
  Results: {
    purpose:
      "Review saved outcomes, compare equivalent runs, and inspect action replays or exports.",
    next: "Reference passes test the software. Only actual model runs measure AI performance. Filters change the view, not the saved history; exports include all saved runs.",
  },
};

export function WorkspaceHelp() {
  return (
    <details className="workspace-help card">
      <summary>Starting fresh, resetting previews and keeping results</summary>
      <div>
        <p>
          <b>New trial:</b> browser cookies, form entries and checkout state
          reset automatically. You do not need to clear them.
        </p>
        <p>
          <b>Reset preview:</b> starts a new practice checkout only. It does not
          delete results or reset an active batch.
        </p>
        <p>
          <b>Reset setup:</b> restores the software-check selection and default
          settings. Saved results are retained.
        </p>
        <p>
          <b>Empty results for a new suite:</b> stop the batch, stop the server
          with Ctrl+C in its terminal, then run this from the repository
          directory. Each start uses a new results folder; your original history
          and API configuration are preserved.
        </p>
        <pre>
          BENCH_DATA_DIR="data/suites/$(date +%Y%m%d-%H%M%S)" ./scripts/start.sh
        </pre>
        <p>
          Refresh this page after restarting. Start normally with{" "}
          <code>./scripts/start.sh</code> to return to the original results
          folder. There is no delete-history action in this UI.
        </p>
      </div>
    </details>
  );
}

export default function Guide({
  navigate,
  setup,
  ready,
}: {
  navigate: (tab: string) => void;
  setup: (full: boolean) => void;
  ready: boolean;
}) {
  return (
    <>
      <section className="start-panel card">
        <div className="eyebrow">CHOOSE YOUR NEXT STEP</div>
        <h2>Validate the software first. Evaluate models when ready.</h2>
        <p>
          All checkouts are local simulations. A reference pass means the task
          works as programmed; it is not an AI score.
        </p>
        <div className="start-options">
          <div>
            <span className="tag">No model inference</span>
            <h3>Check the benchmark</h3>
            <p>
              Use the deterministic reference to fill forms, follow payment
              steps and verify the evaluator. Start with one scenario or prepare
              the full v2.1 suite.
            </p>
            <div className="actions">
              <button
                className="button primary"
                disabled={!ready}
                onClick={() => setup(false)}
              >
                Set up a quick software check
              </button>
              <button
                className="button secondary"
                disabled={!ready}
                onClick={() => setup(true)}
              >
                Set up all v2.1 checks
              </button>
            </div>
            <small>
              Both options prepare a batch. You review it before it starts.
            </small>
          </div>
          <div>
            <span className="tag">Requires a model or endpoint</span>
            <h3>Evaluate an AI system</h3>
            <p>
              Select a configured model, then use the same scenarios and budgets
              for comparison. API calls may incur charges; local models use your
              hardware.
            </p>
            <button
              className="button secondary"
              onClick={() => navigate("Models")}
            >
              Choose models →
            </button>
          </div>
        </div>
      </section>
      <div className="section-map">
        {(
          [
            ["Models", "01", "Choose the decision-maker"],
            ["Scenarios", "02", "Choose tasks and review the batch"],
            ["Live session", "03", "Watch execution and control the queue"],
            ["Results", "04", "Inspect outcomes and replay actions"],
          ] as const
        ).map(([name, number, description]) => (
          <button key={name} className="card" onClick={() => navigate(name)}>
            <span className="section-number">{number}</span>
            <b>{name}</b>
            <small>{description}</small>
          </button>
        ))}
      </div>
      <section className="card how-it-works">
        <h2>What happens during a test?</h2>
        <div className="explanation-grid">
          <div>
            <b>1. Decide</b>
            <p>
              The reference uses programmed rules. In an AI run, the chosen
              model supplies the decisions appropriate to its role; any
              controller assistance is recorded separately.
            </p>
          </div>
          <div>
            <b>2. Act in a browser</b>
            <p>
              Browser tooling operates Chromium: typing, clicking, scrolling and
              handling frames or popups. Playwright is browser automation, not
              an AI model.
            </p>
          </div>
          <div>
            <b>3. Check the outcome</b>
            <p>
              The private evaluator checks entered values, consent, handoff and
              transaction state. A displayed QR or a successful click alone does
              not mean payment completion.
            </p>
          </div>
        </div>
        <button className="textbutton" onClick={() => navigate("Coverage")}>
          Explore sources and scenario coverage →
        </button>
      </section>
      <WorkspaceHelp />
    </>
  );
}
