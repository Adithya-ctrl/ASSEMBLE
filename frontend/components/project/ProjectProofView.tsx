"use client";

import { ArrowRight, CheckCircle, Code } from "@phosphor-icons/react";
import { Button } from "@radix-ui/themes";

import type { CreateProjectResponse } from "../../lib/types";
import { humanize } from "../../lib/ui";

export default function ProjectProofView({ response, onOpenInspector }: { response: CreateProjectResponse; onOpenInspector: () => void }) {
  const project = response.project;

  return (
    <section className="project-proof-route" aria-labelledby="project-proof-summary-title">
      <header className="project-proof-summary">
        <div>
          <h2 id="project-proof-summary-title">{project.title}</h2>
          <p>{project.source_initiative_name}. Project status: {humanize(project.status)}.</p>
        </div>
        <span className="proof-verification-status"><CheckCircle aria-hidden="true" size={20} weight="fill" />{humanize(response.verification.status)} verification</span>
      </header>

      <dl className="proof-facts">
        <div><dt>Project ID</dt><dd className="mono">{project.id}</dd></div>
        <div><dt>Source plan</dt><dd className="mono">{project.source_plan_id}</dd></div>
        <div><dt>Source initiative</dt><dd>{project.source_initiative_name}<span className="mono">{project.source_initiative_id}</span></dd></div>
        <div><dt>Fresh verification</dt><dd>{humanize(response.verification.status)}{response.verification.objective_value === null ? "" : ` with objective ${response.verification.objective_value}`}</dd></div>
        <div><dt>Catalyst path</dt><dd className="mono">{project.catalyst_path.length === 0 ? "No catalyst actions" : project.catalyst_path.join(" then ")}</dd></div>
        <div><dt>State lineage</dt><dd className="mono">{project.base_state_id}<ArrowRight aria-hidden="true" size={14} />{project.verified_state_id}</dd></div>
      </dl>

      <section className="catalyst-proof" aria-labelledby="catalyst-proof-title">
        <h3 id="catalyst-proof-title">Catalyst outputs</h3>
        {project.catalyst_outputs.length === 0 ? (
          <p>No catalyst was required. The baseline community was analysed directly.</p>
        ) : (
          <ol>
            {project.catalyst_outputs.map((output) => (
              <li key={output.action_id}>
                <strong>{output.action_id}</strong>
                <span className="mono">{output.predecessor_state_id} to {output.successor_state_id}</span>
                <span>{Object.keys(output.diff.added_capabilities).length} capability groups, {output.diff.added_people.length} people and {Object.keys(output.diff.resource_quantity_changes).length} resource changes</span>
              </li>
            ))}
          </ol>
        )}
      </section>

      <Button className="proof-inspector-action" onClick={onOpenInspector} size="3" type="button" variant="outline"><Code aria-hidden="true" size={18} />Open complete technical evidence</Button>
    </section>
  );
}
