"use client";

import {
  Buildings,
  FolderOpen,
  Heartbeat,
  Lightbulb,
  LockKey,
  UsersThree,
} from "@phosphor-icons/react";
import Image from "next/image";
import { useEffect, useRef } from "react";

import styles from "./CivicScene.module.css";

export type CivicSceneKind = "community" | "initiative" | "project" | "resilience" | "identity" | "overview";

const icons = {
  community: UsersThree,
  initiative: Lightbulb,
  project: FolderOpen,
  resilience: Heartbeat,
  identity: LockKey,
  overview: Buildings,
};

export default function CivicScene({
  kind,
  assetSrc,
  alt = "",
  priority = false,
  className = "",
}: {
  kind: CivicSceneKind;
  assetSrc?: string;
  alt?: string;
  priority?: boolean;
  className?: string;
}) {
  const stageRef = useRef<HTMLDivElement>(null);
  const Icon = icons[kind];

  useEffect(() => {
    const stage = stageRef.current;
    if (!stage) return;
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
    const finePointer = window.matchMedia("(pointer: fine)");
    if (reducedMotion.matches || !finePointer.matches) return;

    let frame = 0;
    let nextX = 0;
    let nextY = 0;
    const render = () => {
      frame = 0;
      stage.style.setProperty("--scene-rotate-x", `${nextY * -4}deg`);
      stage.style.setProperty("--scene-rotate-y", `${nextX * 5}deg`);
    };
    const onPointerMove = (event: PointerEvent) => {
      const bounds = stage.getBoundingClientRect();
      nextX = ((event.clientX - bounds.left) / bounds.width - 0.5) * 2;
      nextY = ((event.clientY - bounds.top) / bounds.height - 0.5) * 2;
      if (!frame) frame = window.requestAnimationFrame(render);
    };
    const onPointerLeave = () => {
      nextX = 0;
      nextY = 0;
      if (!frame) frame = window.requestAnimationFrame(render);
    };

    stage.addEventListener("pointermove", onPointerMove, { passive: true });
    stage.addEventListener("pointerleave", onPointerLeave);
    return () => {
      stage.removeEventListener("pointermove", onPointerMove);
      stage.removeEventListener("pointerleave", onPointerLeave);
      if (frame) window.cancelAnimationFrame(frame);
    };
  }, []);

  return (
    <div className={`${styles.stage} ${styles[kind]} ${assetSrc ? styles.hasAsset : ""} ${className}`} data-scene={kind} ref={stageRef}>
      <div className={styles.sceneWorld}>
        <span aria-hidden="true" className={styles.backPlane} />
        {assetSrc ? (
          <div className={styles.assetPlane}>
            <Image alt={alt} className={styles.asset} fill priority={priority} sizes="(max-width: 767px) 92vw, 48vw" src={assetSrc} />
          </div>
        ) : (
          <div aria-hidden="true" className={styles.pendingAsset}>
            <span className={styles.blockLarge}><Icon size={42} weight="duotone" /></span>
            <span className={styles.blockSmall} />
            <span className={styles.blockTall} />
          </div>
        )}
        <span aria-hidden="true" className={styles.frontPlane} />
      </div>
    </div>
  );
}
