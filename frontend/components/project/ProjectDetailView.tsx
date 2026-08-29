"use client";

import { Check, CheckCircle, WarningCircle, XCircle } from "@phosphor-icons/react";
import Link from "next/link";

import type { CreateProjectResponse } from "../../lib/types";
import { humanize } from "../../lib/ui";

export default function ProjectDetailView({ response }: { response: CreateProjectResponse }) {
  const project = response.project;
  const ready = project.status === "READY";

  return (
    <article className={`project-detail project-detail-route ${ready ? "project-detail-ready" : "project-detail-not-ready"}`} aria-labelledby="project-detail-title">
      <header className="project-detail-hero">
        <div>
          <h2 id="project-detail-title">{project.title}</h2>
          <p>{project.short_description}</p>
        </div>
        <span className={`project-ready-badge ${ready ? "" : "project-not-ready-badge"}`}>
          {ready ? <CheckCircle aria-hidden="true" size={18} weight="fill" /> : <WarningCircle aria-hidden="true" size={18} weight="fill" />}
          {humanize(project.status)}
        </span>
      </header>

      <section className="project-objective" aria-labelledby="project-objective-title">
        <h3 id="project-objective-title">Objective</h3>
        <p>{project.objective}</p>
      </section>

      <dl className="project-facts">
        <div><dt>When</dt><dd>{humanize(project.schedule.start_slot)} to {humanize(project.schedule.end_slot)}, across {project.schedule.duration_slots} time blocks</dd></div>
        <div><dt>Where</dt><dd>{project.venue.venue_name}, with room for {project.participant_capacity} people</dd></div>
        <div><dt>Host organisation</dt><dd>{project.host_organisation_name}</dd></div>
        <div><dt>Source</dt><dd>{project.base_state_id === project.verified_state_id ? "Verified from the baseline community" : "Verified after the planned community update"}</dd></div>
      </dl>

      <div className="project-detail-grid">
        <section aria-labelledby="operational-team-title">
          <h3 id="operational-team-title">Operational team</h3>
          <ul className="assignment-list">
            {project.operational_assignments.map((assignment) => (
              <li key={assignment.role_id}>
                <span className="assignment-status"><Check aria-hidden="true" size={15} weight="bold" /></span>
                <div>
                  <strong>{assignment.role_label}</strong>
                  <span>{assignment.person_name}, {assignment.organisation_name}</span>
                  <small>{[...assignment.person_capabilities, ...assignment.person_languages].map(humanize).join(", ") || "Availability matched"}</small>
                </div>
              </li>
            ))}
          </ul>
        </section>

        <section aria-labelledby="readiness-title">
          <h3 id="readiness-title">Readiness</h3>
          <ul className="readiness-list">
            {project.readiness.checks.map((check) => (
              <li className={check.ready ? "readiness-ready" : "readiness-missing"} key={check.check_id}>
                {check.ready ? <CheckCircle aria-hidden="true" size={17} weight="fill" /> : <XCircle aria-hidden="true" size={17} weight="fill" />}
                <div>
                  <strong>{check.ready ? "Ready: " : "Missing: "}{check.label}</strong>
                  <span>{check.evidence.map(humanize).join(", ") || "No supporting evidence returned"}</span>
                </div>
              </li>
            ))}
          </ul>
        </section>
      </div>

      <div className="project-detail-grid project-detail-grid-compact">
        <section>
          <h3>Resources and access</h3>
          {project.resources.map((resource) => <p key={resource.resource_id}><strong>{resource.resource_name}</strong><br />{resource.quantity_required} allocated from {resource.quantity_available} available</p>)}
          <p><strong>Accessibility</strong><br />{project.accessibility_requirements.map(humanize).join(", ") || "No additional requirements declared"}</p>
        </section>
        <section>
          <h3>Capabilities and languages</h3>
          <p><strong>Capabilities</strong><br />{project.capability_modules.map(humanize).join(", ")}</p>
          <p><strong>Operational languages</strong><br />{project.supported_languages.map(humanize).join(", ")}</p>
        </section>
      </div>

      <footer className="project-proof-footer">
        <span>{ready ? <CheckCircle aria-hidden="true" size={16} weight="fill" /> : <WarningCircle aria-hidden="true" size={16} weight="fill" />}Fresh server verification: {humanize(response.verification.status)}. Project status: {humanize(project.status)}.</span>
        <Link className="secondary-link" href="/projects/proof">View Project proof</Link>
      </footer>
    </article>
  );
}
