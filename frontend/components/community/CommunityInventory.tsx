"use client";

import {
  Buildings,
  Check,
  GitBranch,
  ListChecks,
  Toolbox,
  UserCircle,
  X,
} from "@phosphor-icons/react";
import { useMemo, useRef, useState, type KeyboardEvent } from "react";

import type { CommunityState, PersonBlock, ResourceBlock, SpaceBlock } from "../../lib/types";
import { humanize } from "../../lib/ui";

type Category = "overview" | "people" | "places" | "resources";
type ViewMode = "graph" | "list";
type FocusTarget = Pick<HTMLElement, "focus" | "isConnected">;
type EntityView =
  | { kind: "person"; id: string; name: string; organisationName: string; availability: string; taskFact: string; source: PersonBlock }
  | { kind: "space"; id: string; name: string; organisationName: string; availability: string; taskFact: string; source: SpaceBlock }
  | { kind: "resource"; id: string; name: string; organisationName: string; availability: string; taskFact: string; source: ResourceBlock };

const CATEGORIES: Array<{ id: Category; label: string }> = [
  { id: "overview", label: "Overview" },
  { id: "people", label: "People" },
  { id: "places", label: "Places" },
  { id: "resources", label: "Resources" },
];

export function focusIfConnected(target: FocusTarget | null | undefined): boolean {
  if (!target?.isConnected) return false;
  target.focus();
  return true;
}

function formatSlots(slots: readonly string[]): string {
  return slots.map((slot) => humanize(slot).replace("Sat ", "Saturday ")).join(", ");
}

function EntityIcon({ kind }: { kind: EntityView["kind"] }) {
  if (kind === "person") return <UserCircle aria-hidden="true" size={22} weight="duotone" />;
  if (kind === "space") return <Buildings aria-hidden="true" size={22} weight="duotone" />;
  return <Toolbox aria-hidden="true" size={22} weight="duotone" />;
}

function countLabel(count: number, singular: string, plural = `${singular}s`): string {
  return `${count} ${count === 1 ? singular : plural}`;
}

function EntityDetail({ entity, judgeMode, onClose }: { entity: EntityView; judgeMode: boolean; onClose: () => void }) {
  const source = entity.source;
  return (
    <aside aria-labelledby="community-detail-title" className="community-entity-detail" tabIndex={-1}>
      <div className="community-detail-heading">
        <div><span className="community-detail-type">{humanize(entity.kind)}</span><h2 id="community-detail-title">{entity.name}</h2></div>
        <button aria-label="Close details" onClick={onClose} type="button"><X aria-hidden="true" size={18} /></button>
      </div>
      <dl className="community-detail-facts">
        <div><dt>Community context</dt><dd>{entity.organisationName}</dd></div>
        <div><dt>Availability</dt><dd>{formatSlots(source.available_slots)}</dd></div>
        {entity.kind === "person" ? <><div><dt>Capabilities</dt><dd>{entity.source.capabilities.map(humanize).join(", ") || "Learning capacity"}</dd></div><div><dt>Languages</dt><dd>{entity.source.languages.map((language) => language.toUpperCase()).join(", ") || "None declared"}</dd></div><div><dt>Learning interests</dt><dd>{entity.source.willing_to_learn.map(humanize).join(", ") || "None declared"}</dd></div><div><dt>Contribution limit</dt><dd>{entity.source.max_contribution_slots} time blocks</dd></div></> : null}
        {entity.kind === "space" ? <><div><dt>Capacity</dt><dd>{entity.source.capacity} people</dd></div><div><dt>Features</dt><dd>{entity.source.features.map(humanize).join(", ")}</dd></div></> : null}
        {entity.kind === "resource" ? <><div><dt>Available quantity</dt><dd>{entity.source.quantity}</dd></div><div><dt>Sharing</dt><dd>{entity.source.shareable ? "Available for community sharing" : "Not marked shareable"}</dd></div></> : null}
      </dl>
      <details className="community-technical-details" open={judgeMode}>
        <summary>Technical details</summary>
        <dl><div><dt>Reference ID</dt><dd className="mono">{entity.id}</dd></div><div><dt>Exact slots</dt><dd className="mono">{source.available_slots.join(", ")}</dd></div></dl>
      </details>
    </aside>
  );
}

export default function CommunityInventory({ community, selectedId, viewMode, judgeMode, onSelect, onViewModeChange, onAnnounce }: { community: CommunityState; selectedId: string; viewMode: ViewMode; judgeMode: boolean; onSelect: (id: string) => void; onViewModeChange: (view: ViewMode) => void; onAnnounce: (message: string) => void }) {
  const [category, setCategory] = useState<Category>("overview");
  const detailRef = useRef<HTMLDivElement>(null);
  const entityTriggerRefs = useRef(new Map<string, HTMLButtonElement>());
  const organisationNames = useMemo(() => new Map(community.organisations.map((organisation) => [organisation.id, organisation.name])), [community.organisations]);
  const entities = useMemo<EntityView[]>(() => {
    if (category === "people") return community.people.map((person) => ({ kind: "person", id: person.id, name: person.name, organisationName: organisationNames.get(person.organisation_id) ?? "Community organisation", availability: countLabel(person.available_slots.length, "available time block"), taskFact: person.capabilities.slice(0, 2).map(humanize).join(" and ") || "Open to learning", source: person }));
    if (category === "places") return community.spaces.map((space) => ({ kind: "space", id: space.id, name: space.name, organisationName: organisationNames.get(space.organisation_id) ?? "Community organisation", availability: countLabel(space.available_slots.length, "available time block"), taskFact: `Capacity for ${space.capacity}, ${humanize(space.features[0] ?? "shared space").toLowerCase()}`, source: space }));
    if (category === "resources") return community.resources.map((resource) => ({ kind: "resource", id: resource.id, name: resource.name, organisationName: organisationNames.get(resource.organisation_id) ?? "Community organisation", availability: countLabel(resource.available_slots.length, "available time block"), taskFact: `${resource.quantity} available, ${resource.shareable ? "shareable" : "reserved"}`, source: resource }));
    return [];
  }, [category, community.people, community.resources, community.spaces, organisationNames]);
  const selected = entities.find((entity) => entity.id === selectedId) ?? null;

  const chooseCategory = (nextCategory: Category) => {
    setCategory(nextCategory);
    onSelect("");
    onAnnounce(`${CATEGORIES.find((item) => item.id === nextCategory)?.label ?? "Community"} category selected.`);
  };
  const handleCategoryKeys = (event: KeyboardEvent<HTMLDivElement>) => {
    if (!(["ArrowLeft", "ArrowRight", "Home", "End"] as string[]).includes(event.key)) return;
    event.preventDefault();
    const currentIndex = CATEGORIES.findIndex((item) => item.id === category);
    const nextIndex = event.key === "Home" ? 0 : event.key === "End" ? CATEGORIES.length - 1 : (currentIndex + (event.key === "ArrowRight" ? 1 : -1) + CATEGORIES.length) % CATEGORIES.length;
    const next = CATEGORIES[nextIndex];
    chooseCategory(next.id);
    requestAnimationFrame(() => document.getElementById(`community-tab-${next.id}`)?.focus());
  };
  const selectEntity = (entity: EntityView) => {
    onSelect(entity.id);
    onAnnounce(`${entity.name} details opened.`);
    requestAnimationFrame(() => detailRef.current?.querySelector<HTMLElement>(".community-entity-detail")?.focus());
  };
  const closeSelectedEntity = () => {
    if (!selected) return;
    const selectedEntityId = selected.id;
    const selectedEntityName = selected.name;
    onSelect("");
    onAnnounce(`${selectedEntityName} details closed.`);
    requestAnimationFrame(() => focusIfConnected(entityTriggerRefs.current.get(selectedEntityId)));
  };
  const selectedCategoryLabel = CATEGORIES.find((item) => item.id === category)?.label ?? "Community";

  return (
    <section className="community-inventory" aria-labelledby="community-inventory-title">
      <div aria-label="Community category" className="community-category-tabs" onKeyDown={handleCategoryKeys} role="tablist">
        {CATEGORIES.map((item) => <button aria-controls="community-category-panel" aria-selected={category === item.id} id={`community-tab-${item.id}`} key={item.id} onClick={() => chooseCategory(item.id)} role="tab" tabIndex={category === item.id ? 0 : -1} type="button">{item.label}</button>)}
      </div>
      <div aria-labelledby={`community-tab-${category}`} id="community-category-panel" role="tabpanel">
        {category === "overview" ? (
          <div className="community-overview">
            <div className="community-overview-copy">
              <h2 id="community-inventory-title">Capacity across the community</h2>
              <p>{countLabel(community.people.length, "person", "people")}, {countLabel(community.spaces.length, "shared place")}, and {countLabel(community.resources.length, "resource pool")} are available across {countLabel(community.organisations.length, "local organisation")}.</p>
            </div>
            <ul aria-label="Participating organisations">
              {community.organisations.map((organisation) => {
                const people = community.people.filter((person) => person.organisation_id === organisation.id).length;
                const places = community.spaces.filter((space) => space.organisation_id === organisation.id).length;
                const resources = community.resources.filter((resource) => resource.organisation_id === organisation.id).length;
                return <li key={organisation.id}><Buildings aria-hidden="true" size={21} weight="duotone" /><span><strong>{organisation.name}</strong><small>{countLabel(people, "person", "people")}, {countLabel(places, "place")}, {countLabel(resources, "resource pool")}</small></span>{judgeMode ? <small className="mono">{organisation.id}</small> : null}</li>;
              })}
            </ul>
          </div>
        ) : (
          <div className={`community-category-layout ${selected ? "community-category-layout-selected" : ""}`}>
            <div className="community-category-main">
              <div className="community-category-toolbar">
                <div><h2 id="community-inventory-title">{selectedCategoryLabel}</h2><p>{countLabel(entities.length, category === "people" ? "person" : category === "places" ? "place" : "resource pool", category === "people" ? "people" : undefined)}</p></div>
                <fieldset><legend>Preferred inventory view</legend><button aria-label="Graph view" aria-pressed={viewMode === "graph"} onClick={() => { onViewModeChange("graph"); onAnnounce("Community graph view enabled."); }} type="button"><GitBranch aria-hidden="true" size={17} /><span>Graph</span></button><button aria-label="List view" aria-pressed={viewMode === "list"} onClick={() => { onViewModeChange("list"); onAnnounce("Community list view enabled."); }} type="button"><ListChecks aria-hidden="true" size={17} /><span>List</span></button></fieldset>
              </div>
              {entities.length > 0 ? (
                <div className={`community-entity-collection community-entity-${viewMode}`} data-category={category}>
                  {entities.map((entity) => (
                    <button aria-pressed={selectedId === entity.id} className="community-entity-row" key={entity.id} onClick={() => selectEntity(entity)} ref={(node) => { if (node) entityTriggerRefs.current.set(entity.id, node); else entityTriggerRefs.current.delete(entity.id); }} type="button">
                      <span className="community-entity-icon"><EntityIcon kind={entity.kind} /></span>
                      <span className="community-entity-copy"><strong>{entity.name}</strong><small>{entity.organisationName}</small><span className="community-entity-facts"><span>{entity.availability}</span><span>{entity.taskFact}</span></span></span>
                      {selectedId === entity.id ? <Check aria-label="Selected" size={17} weight="bold" /> : null}
                    </button>
                  ))}
                </div>
              ) : <div className="community-empty-category"><strong>No capacity in this category</strong><span>Choose another category to continue.</span></div>}
            </div>
            {selected ? <div className="community-detail-surface" ref={detailRef}><EntityDetail entity={selected} judgeMode={judgeMode} onClose={closeSelectedEntity} /></div> : null}
          </div>
        )}
      </div>
    </section>
  );
}
