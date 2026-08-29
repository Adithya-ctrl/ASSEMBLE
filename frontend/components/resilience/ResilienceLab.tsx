"use client";

import {
  type FormEvent,
  type KeyboardEvent,
  useId,
  useMemo,
  useRef,
  useState,
} from "react";

import type {
  ResilienceLabProps,
  ResilienceMode,
} from "../../lib/resilience-types";
import {
  NON_OPERATIONAL_EVIDENCE_NOTICE,
  buildFrontierViewModel,
  buildRecoveryViewModel,
  buildStressViewModel,
  technicalDisclosureState,
  type FrontierViewModel,
  type RecoveryViewModel,
  type StressViewModel,
  type ViewPhase,
} from "../../lib/resilience-view-model";
import CivicScene from "../visual/CivicScene";
import { RESILIENCE_SCENE } from "../visual/sceneAssets";
import styles from "./ResilienceLab.module.css";

const MODES: ReadonlyArray<{ id: ResilienceMode; label: string; shortLabel: string }> = [
  { id: "stress", label: "Stress test", shortLabel: "Stress" },
  { id: "recovery", label: "Recovery", shortLabel: "Recovery" },
  { id: "frontier", label: "Capability frontier", shortLabel: "Frontier" },
];

function classes(...values: Array<string | false | undefined>): string {
  return values.filter(Boolean).join(" ");
}

function toneClass(status: string): string {
  if (status === "RESILIENT" || status === "OPTIMAL" || status === "FEASIBLE") return styles.tonePositive;
  if (status === "CRITICAL" || status === "INFEASIBLE") return styles.toneCritical;
  if (status === "UNKNOWN") return styles.toneUnknown;
  return styles.toneCaution;
}

function TechnicalEvidence({
  facts,
  judgeMode,
  label = "Technical evidence",
}: {
  facts: Array<{ label: string; value: string }>;
  judgeMode: boolean;
  label?: string;
}) {
  if (facts.length === 0) return null;
  const disclosure = technicalDisclosureState(judgeMode);
  return (
    <details
      key={disclosure.instanceKey}
      className={styles.technical}
      open={disclosure.forcedOpen}
      onToggle={(event) => {
        if (judgeMode && !event.currentTarget.open) event.currentTarget.open = true;
      }}
    >
      <summary>{judgeMode ? `${label}, Judge mode` : label}</summary>
      <dl>
        {facts.map((fact) => (
          <div key={`${fact.label}-${fact.value}`}>
            <dt>{fact.label}</dt>
            <dd>{fact.value}</dd>
          </div>
        ))}
      </dl>
    </details>
  );
}

function PhaseMessage({
  phase,
  headline,
  description,
}: {
  phase: ViewPhase;
  headline: string;
  description: string;
}) {
  if (phase === "ready") return null;
  return (
    <div
      className={classes(styles.phaseMessage, phase === "error" || phase === "invalid" ? styles.phaseError : undefined)}
      role={phase === "error" || phase === "invalid" ? "alert" : "status"}
    >
      {phase === "loading" ? <span className={styles.activityDot} aria-hidden="true" /> : null}
      <div>
        <h3>{headline}</h3>
        <p>{description}</p>
      </div>
    </div>
  );
}

function Metric({ label, value, hint }: { label: string; value: string | number; hint?: string }) {
  return (
    <div className={styles.metric}>
      <dt>{label}</dt>
      <dd>{value}</dd>
      {hint ? <span>{hint}</span> : null}
    </div>
  );
}

function StressPanel({
  view,
  props,
  selectedInitiativeId,
  onSelectedInitiative,
  idPrefix,
}: {
  view: StressViewModel;
  props: ResilienceLabProps;
  selectedInitiativeId: string;
  onSelectedInitiative: (initiativeId: string) => void;
  idPrefix: string;
}) {
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!selectedInitiativeId || props.stress.loading) return;
    props.onRunStress({
      sourceStateId: props.source.stateId,
      sourceContentHash: props.source.contentHash,
      catalystPath: props.source.catalystPath.map((item) => item.id),
      initiativeId: selectedInitiativeId,
    });
  };
  return (
    <div className={styles.panelBody}>
      <div className={styles.taskIntro}>
        <div>
          <p className={styles.kicker}>Stress test</p>
          <h2>What single disruption would stop this plan?</h2>
          <p>Test every server-returned one-fact change against the same proved source.</p>
        </div>
        <form className={styles.runForm} onSubmit={submit}>
          <label htmlFor={`${idPrefix}-initiative`}>Buildable initiative</label>
          <div className={styles.formRow}>
            <select
              id={`${idPrefix}-initiative`}
              value={selectedInitiativeId}
              onChange={(event) => onSelectedInitiative(event.target.value)}
              disabled={props.initiatives.length === 0 || props.stress.loading}
            >
              {props.initiatives.length === 0 ? <option value="">No buildable initiatives</option> : null}
              {props.initiatives.map((initiative) => (
                <option key={initiative.id} value={initiative.id}>{initiative.label}</option>
              ))}
            </select>
            <button
              className={styles.primaryButton}
              type="submit"
              disabled={!selectedInitiativeId || props.stress.loading}
            >
              {props.stress.loading ? "Testing…" : "Run stress test"}
            </button>
          </div>
        </form>
      </div>

      <PhaseMessage phase={view.phase} headline={view.headline} description={view.description} />
      {view.phase === "ready" ? (
        <div className={styles.resultStack}>
          <section className={styles.resultHero} aria-labelledby={`${idPrefix}-result`}>
            <div>
              <p className={styles.kicker}>Stress result</p>
              <h3 id={`${idPrefix}-result`}>{view.headline}</h3>
              <p>{view.description}</p>
            </div>
            <div className={styles.ratio} aria-label={`Resilience ratio ${view.ratioLabel}`}>
              <strong>{view.ratioLabel}</strong>
              <span>resilience</span>
            </div>
          </section>
          <dl className={styles.metrics}>
            <Metric label="Tested" value={view.catalogueSize} hint="complete catalogue" />
            <Metric label="Decisive" value={view.decisiveCount} />
            <Metric label="Resilient" value={view.resilientCount} />
            <Metric label="Degraded" value={view.degradedCount} />
            <Metric label="Critical" value={view.criticalCount} />
            <Metric label="Unknown" value={view.unknownCount} hint="excluded from ratio" />
          </dl>
          <section aria-labelledby={`${idPrefix}-outcomes`}>
            <div className={styles.sectionHeading}>
              <div>
                <p className={styles.kicker}>One fact at a time</p>
                <h3 id={`${idPrefix}-outcomes`}>Before and after</h3>
              </div>
              <span>{view.outcomes.length} returned disruptions</span>
            </div>
            <div className={styles.cardGrid}>
              {view.outcomes.map((outcome) => (
                <article className={styles.outcomeCard} key={outcome.perturbationId}>
                  <div className={styles.cardHeading}>
                    <span className={styles.typeLabel}>{outcome.typeLabel}</span>
                    <span className={classes(styles.statusBadge, toneClass(outcome.criticality))}>
                      {outcome.statusLabel}
                    </span>
                  </div>
                  <h4>{outcome.label}</h4>
                  <p>{outcome.beforeAfter}</p>
                  <p className={styles.meaning}>{outcome.meaning}</p>
                  <TechnicalEvidence facts={outcome.technical} judgeMode={props.judgeMode} label="Outcome evidence" />
                </article>
              ))}
            </div>
          </section>
          <TechnicalEvidence facts={view.technical} judgeMode={props.judgeMode} />
        </div>
      ) : null}
    </div>
  );
}

function RecoveryPanel({
  view,
  stressView,
  props,
  selectedPerturbationId,
  onSelectedPerturbation,
  idPrefix,
}: {
  view: RecoveryViewModel;
  stressView: StressViewModel;
  props: ResilienceLabProps;
  selectedPerturbationId: string;
  onSelectedPerturbation: (perturbationId: string) => void;
  idPrefix: string;
}) {
  const selected = stressView.outcomes.find((item) => item.perturbationId === selectedPerturbationId);
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!selected || props.recovery.loading) return;
    props.onRunRecovery({
      sourceStateId: props.source.stateId,
      sourceContentHash: selected.binding.source_content_hash,
      catalystPath: props.source.catalystPath.map((item) => item.id),
      initiativeId: selected.binding.initiative_id,
      perturbationId: selected.perturbationId,
      perturbationBinding: selected.binding,
    });
  };
  return (
    <div className={styles.panelBody}>
      <div className={styles.taskIntro}>
        <div>
          <p className={styles.kicker}>Recovery</p>
          <h2>Can the selected disruption be recovered?</h2>
          <p>Stage 1 proves the fewest changed assignments. Stage 2 then minimises normal burden.</p>
        </div>
        <form className={styles.runForm} onSubmit={submit}>
          <label htmlFor={`${idPrefix}-perturbation`}>Returned stress disruption</label>
          <div className={styles.formRow}>
            <select
              id={`${idPrefix}-perturbation`}
              value={selectedPerturbationId}
              onChange={(event) => onSelectedPerturbation(event.target.value)}
              disabled={stressView.outcomes.length === 0 || props.recovery.loading}
            >
              {stressView.outcomes.length === 0 ? <option value="">Run a current stress test first</option> : null}
              {stressView.outcomes.map((outcome) => (
                <option key={outcome.perturbationId} value={outcome.perturbationId}>
                  {outcome.label}, {outcome.statusLabel}
                </option>
              ))}
            </select>
            <button
              className={styles.primaryButton}
              type="submit"
              disabled={!selected || props.recovery.loading}
            >
              {props.recovery.loading ? "Recovering…" : "Find recovery"}
            </button>
          </div>
        </form>
      </div>

      <PhaseMessage phase={view.phase} headline={view.headline} description={view.description} />
      {view.phase === "ready" ? (
        <div className={styles.resultStack}>
          <section className={styles.resultHero} aria-labelledby={`${idPrefix}-result`}>
            <div>
              <p className={styles.kicker}>Recovery result</p>
              <h3 id={`${idPrefix}-result`}>{view.headline}</h3>
              <p>{view.description}</p>
            </div>
            <span className={classes(styles.statusBadge, toneClass(view.statusLabel.toUpperCase()))}>
              {view.statusLabel}
            </span>
          </section>
          <dl className={styles.metrics}>
            <Metric label="Minimum changed" value={view.minimumLabel} />
            <Metric label="Recovered burden" value={view.burdenLabel} />
          </dl>
          <div className={styles.stageGrid}>
            {view.stage1 ? (
              <section className={styles.stageCard} aria-labelledby={`${idPrefix}-stage-one`}>
                <span>Stage 1</span>
                <h3 id={`${idPrefix}-stage-one`}>Minimum change, {view.stage1.status}</h3>
                <p>{view.stage1.claim}</p>
              </section>
            ) : null}
            <section className={styles.stageCard} aria-labelledby={`${idPrefix}-stage-two`}>
              <span>Stage 2</span>
              <h3 id={`${idPrefix}-stage-two`}>
                {view.stage2 ? `Secondary burden, ${view.stage2.status}` : "Not run"}
              </h3>
              <p>{view.stage2?.claim ?? "Stage 2 is withheld until Stage 1 proves the minimum."}</p>
            </section>
          </div>
          {view.roleDiffs.length > 0 ? (
            <section aria-labelledby={`${idPrefix}-assignments`}>
              <div className={styles.sectionHeading}>
                <div>
                  <p className={styles.kicker}>Exact assignment receipt</p>
                  <h3 id={`${idPrefix}-assignments`}>What changed</h3>
                </div>
              </div>
              <ul className={styles.diffList}>
                {view.roleDiffs.map((item) => (
                  <li key={item.roleId}>
                    <span className={classes(styles.diffMarker, item.changed ? styles.diffChanged : styles.diffPreserved)} aria-hidden="true" />
                    <div>
                      <strong>{item.roleLabel}</strong>
                      <span>{item.summary}</span>
                    </div>
                    <span className={styles.diffState}>{item.changed ? "Changed" : "Preserved"}</span>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}
          <TechnicalEvidence facts={view.technical} judgeMode={props.judgeMode} />
        </div>
      ) : null}
    </div>
  );
}

function Bucket({ label, values, tone }: { label: string; values: string[]; tone: string }) {
  return (
    <div className={styles.bucket}>
      <span className={classes(styles.bucketLabel, tone)}>{label}: {values.length}</span>
      <p>{values.length > 0 ? values.join(", ") : "None"}</p>
    </div>
  );
}

function FrontierPanel({
  view,
  props,
  idPrefix,
}: {
  view: FrontierViewModel;
  props: ResilienceLabProps;
  idPrefix: string;
}) {
  const run = () => {
    if (props.frontier.loading || props.frontierExpectations.initiativeIds.length === 0) return;
    props.onRunFrontier({
      sourceStateId: props.source.stateId,
      sourceContentHash: props.source.contentHash,
      catalystPath: props.source.catalystPath.map((item) => item.id),
      expectedInitiativeIds: props.frontierExpectations.initiativeIds,
      expectedActionIds: props.frontierExpectations.actionIds,
    });
  };
  return (
    <div className={styles.panelBody}>
      <div className={styles.taskIntro}>
        <div>
          <p className={styles.kicker}>Capability frontier</p>
          <h2>Which single action changes what is buildable?</h2>
          <p>Every action is compared independently from this source. Results are not an action sequence.</p>
        </div>
        <button
          className={styles.primaryButton}
          type="button"
          onClick={run}
          disabled={props.frontier.loading || props.frontierExpectations.initiativeIds.length === 0}
        >
          {props.frontier.loading ? "Comparing…" : "Compare actions"}
        </button>
      </div>

      <PhaseMessage phase={view.phase} headline={view.headline} description={view.description} />
      {view.phase === "ready" ? (
        <div className={styles.resultStack}>
          <section className={styles.resultHero} aria-labelledby={`${idPrefix}-result`}>
            <div>
              <p className={styles.kicker}>Capability frontier</p>
              <h3 id={`${idPrefix}-result`}>{view.headline}</h3>
              <p>{view.description}</p>
            </div>
            <div className={styles.leverage}>
              <span>Highest leverage</span>
              <strong>{view.highestLeverageLabel}</strong>
            </div>
          </section>
          <section aria-labelledby={`${idPrefix}-baseline`}>
            <div className={styles.sectionHeading}>
              <div>
                <p className={styles.kicker}>Before any candidate</p>
                <h3 id={`${idPrefix}-baseline`}>Baseline capability</h3>
              </div>
            </div>
            <div className={styles.bucketGrid}>
              <Bucket label="Buildable" values={view.baselineBuildable} tone={styles.tonePositive} />
              <Bucket label="Blocked" values={view.baselineBlocked} tone={styles.toneCritical} />
              <Bucket label="Unknown" values={view.baselineUnknown} tone={styles.toneUnknown} />
            </div>
          </section>
          <section aria-labelledby={`${idPrefix}-actions`}>
            <div className={styles.sectionHeading}>
              <div>
                <p className={styles.kicker}>Independent candidates</p>
                <h3 id={`${idPrefix}-actions`}>Action evidence</h3>
              </div>
              <span>{view.actions.length} actions assessed</span>
            </div>
            <div className={styles.actionGrid}>
              {view.actions.map((action) => (
                <article className={classes(styles.actionCard, !action.applicable && styles.actionUnavailable)} key={action.actionId}>
                  <div className={styles.cardHeading}>
                    <span className={classes(styles.statusBadge, action.applicable ? styles.tonePositive : styles.toneNeutral)}>
                      {action.applicabilityLabel}
                    </span>
                    <span className={styles.cost}>{action.costLabel}</span>
                  </div>
                  <h4>{action.name}</h4>
                  <div className={styles.badgeRow}>
                    {action.isHighestLeverage ? <span className={styles.leverageBadge}>Highest leverage</span> : null}
                    {action.isPareto ? <span className={styles.paretoBadge}>Pareto-efficient</span> : null}
                  </div>
                  <dl className={styles.actionFacts}>
                    <div><dt>Newly feasible</dt><dd>{action.newlyFeasible.join(", ") || "None"}</dd></div>
                    <div><dt>Lost</dt><dd>{action.lostFeasible.join(", ") || "None"}</dd></div>
                    <div><dt>Unknown</dt><dd>{action.unknown.join(", ") || "None"}</dd></div>
                    <div><dt>Coverage</dt><dd>{action.coverageLabel}</dd></div>
                  </dl>
                  <p className={styles.meaning}>{action.explanation}</p>
                  <TechnicalEvidence facts={action.technical} judgeMode={props.judgeMode} label="Action evidence" />
                </article>
              ))}
            </div>
          </section>
          <TechnicalEvidence facts={view.technical} judgeMode={props.judgeMode} />
        </div>
      ) : null}
    </div>
  );
}

export default function ResilienceLab(props: ResilienceLabProps) {
  const baseId = useId();
  const [mode, setMode] = useState<ResilienceMode>("stress");
  const [initiativeSelection, setInitiativeSelection] = useState(props.initiatives[0]?.id ?? "");
  const [perturbationSelection, setPerturbationSelection] = useState("");
  const tabRefs = useRef<Array<HTMLButtonElement | null>>([]);
  const selectedInitiativeId = props.initiatives.some((item) => item.id === initiativeSelection)
    ? initiativeSelection
    : (props.initiatives[0]?.id ?? "");
  const stressView = useMemo(
    () => buildStressViewModel(props.stress, props.source),
    [props.source, props.stress],
  );
  const recoveryView = useMemo(
    () => buildRecoveryViewModel(props.recovery, props.source, stressView),
    [props.recovery, props.source, stressView],
  );
  const frontierView = useMemo(
    () => buildFrontierViewModel(props.frontier, props.source),
    [props.frontier, props.source],
  );
  const selectedPerturbationId = stressView.outcomes.some(
    (item) => item.perturbationId === perturbationSelection,
  )
    ? perturbationSelection
    : (stressView.outcomes[0]?.perturbationId ?? "");
  const activeView = mode === "stress" ? stressView : mode === "recovery" ? recoveryView : frontierView;

  const selectTab = (index: number) => {
    const next = MODES[index];
    setMode(next.id);
    tabRefs.current[index]?.focus();
  };
  const handleTabKey = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    let nextIndex: number | null = null;
    if (event.key === "ArrowRight") nextIndex = (index + 1) % MODES.length;
    if (event.key === "ArrowLeft") nextIndex = (index - 1 + MODES.length) % MODES.length;
    if (event.key === "Home") nextIndex = 0;
    if (event.key === "End") nextIndex = MODES.length - 1;
    if (nextIndex === null) return;
    event.preventDefault();
    selectTab(nextIndex);
  };

  return (
    <section className={styles.lab} aria-labelledby={`${baseId}-title`}>
      <header className={styles.labHeader}>
        <div className={styles.heroCopy}>
          <h1 id={`${baseId}-title`}>Pressure-test the proof before it becomes a promise</h1>
          <p>Explore structural risk, minimum-disruption recovery, and one-action capability without changing the live workflow.</p>
        </div>
        <CivicScene
          alt="A community bridge rebuilt from modular blocks after a disruption"
          assetSrc={RESILIENCE_SCENE}
          className={classes(
            styles.heroScene,
            mode === "stress" ? styles.heroStress : mode === "recovery" ? styles.heroRecovery : styles.heroFrontier,
          )}
          kind="resilience"
        />
        <div className={styles.sourceCard}>
          <span>Current source</span>
          <strong>{props.source.label}</strong>
          <small>
            {props.source.catalystPath.length === 0
              ? "Declared community with no catalyst applied"
              : props.source.catalystPath.map((item) => item.label).join(", then ")}
          </small>
          <TechnicalEvidence
            judgeMode={props.judgeMode}
            label="Source evidence"
            facts={[
              { label: "Source state", value: props.source.stateId },
              ...(props.source.contentHash
                ? [{ label: "Source content hash", value: props.source.contentHash }]
                : []),
              ...props.source.catalystPath.map((item, index) => ({
                label: `Catalyst ${index + 1}`,
                value: item.id,
              })),
            ]}
          />
        </div>
      </header>

      <aside className={styles.evidenceNotice} aria-label="Analytical evidence boundary">
        <strong>Evidence, not an operation</strong>
        <span>{NON_OPERATIONAL_EVIDENCE_NOTICE}</span>
      </aside>

      <div className={styles.tabs} role="tablist" aria-label="Resilience Lab tasks">
        {MODES.map((item, index) => {
          const active = mode === item.id;
          return (
            <button
              key={item.id}
              id={`${baseId}-tab-${item.id}`}
              ref={(node) => { tabRefs.current[index] = node; }}
              className={styles.tab}
              type="button"
              role="tab"
              aria-selected={active}
              aria-controls={`${baseId}-panel-${item.id}`}
              tabIndex={active ? 0 : -1}
              onClick={() => setMode(item.id)}
              onKeyDown={(event) => handleTabKey(event, index)}
            >
              <span>{index + 1}</span>
              <strong className={styles.tabLongLabel}>{item.label}</strong>
              <strong className={styles.tabShortLabel}>{item.shortLabel}</strong>
            </button>
          );
        })}
      </div>

      {MODES.map((item) => (
        <div
          key={item.id}
          id={`${baseId}-panel-${item.id}`}
          role="tabpanel"
          aria-labelledby={`${baseId}-tab-${item.id}`}
          tabIndex={0}
          hidden={mode !== item.id}
          aria-busy={mode === item.id && activeView.phase === "loading"}
        >
          {item.id === "stress" && mode === "stress" ? (
            <StressPanel
              view={stressView}
              props={props}
              selectedInitiativeId={selectedInitiativeId}
              onSelectedInitiative={setInitiativeSelection}
              idPrefix={`${baseId}-stress`}
            />
          ) : null}
          {item.id === "recovery" && mode === "recovery" ? (
            <RecoveryPanel
              view={recoveryView}
              stressView={stressView}
              props={props}
              selectedPerturbationId={selectedPerturbationId}
              onSelectedPerturbation={setPerturbationSelection}
              idPrefix={`${baseId}-recovery`}
            />
          ) : null}
          {item.id === "frontier" && mode === "frontier" ? (
            <FrontierPanel view={frontierView} props={props} idPrefix={`${baseId}-frontier`} />
          ) : null}
        </div>
      ))}
    </section>
  );
}
