"use client";

import { useCallback, useLayoutEffect, useRef, useState } from "react";
import styles from "./pill-segmented-control.module.css";

export type PillOption<T extends string = string> = {
  value: T;
  label: string;
  disabled?: boolean;
};

type Props<T extends string> = {
  options: PillOption<T>[];
  value: T;
  onChange: (value: T) => void;
  gap?: "default" | "tabs";
  "aria-label"?: string;
};

/**
 * Pill switch: зелёная капсула совпадает с геометрией активной кнопки (getBoundingClientRect).
 * Отступ 2px от серой «подложки» задаётся padding трека + выравнивание по кнопке.
 */
export function PillSegmentedControl<T extends string>({
  options,
  value,
  onChange,
  gap = "default",
  "aria-label": ariaLabel,
}: Props<T>) {
  const trackRef = useRef<HTMLDivElement>(null);
  const optionRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const [indicator, setIndicator] = useState({ x: 0, y: 0, w: 0, h: 0 });

  const updateIndicator = useCallback(() => {
    const track = trackRef.current;
    if (!track) return;
    const idx = options.findIndex((o) => o.value === value);
    if (idx < 0) return;
    const btn = optionRefs.current[idx];
    if (!btn) return;
    const tr = track.getBoundingClientRect();
    const br = btn.getBoundingClientRect();
    setIndicator({
      x: br.left - tr.left,
      y: br.top - tr.top,
      w: br.width,
      h: br.height,
    });
  }, [options, value]);

  useLayoutEffect(() => {
    updateIndicator();
  }, [updateIndicator]);

  useLayoutEffect(() => {
    const track = trackRef.current;
    if (!track) return;
    const ro = new ResizeObserver(() => updateIndicator());
    ro.observe(track);
    optionRefs.current.forEach((el) => {
      if (el) ro.observe(el);
    });
    window.addEventListener("resize", updateIndicator);
    const onScroll = () => updateIndicator();
    window.addEventListener("scroll", onScroll, true);
    let cancelled = false;
    if (typeof document !== "undefined" && document.fonts?.ready) {
      void document.fonts.ready.then(() => {
        if (!cancelled) updateIndicator();
      });
    }
    return () => {
      cancelled = true;
      ro.disconnect();
      window.removeEventListener("resize", updateIndicator);
      window.removeEventListener("scroll", onScroll, true);
    };
  }, [updateIndicator]);

  return (
    <div className={styles.root}>
      <div
        ref={trackRef}
        className={gap === "tabs" ? styles.trackTabs : styles.track}
        role="tablist"
        aria-label={ariaLabel}
      >
        <span
          className={styles.indicator}
          style={{
            transform: `translate3d(${indicator.x}px, ${indicator.y}px, 0)`,
            width: indicator.w > 0 ? indicator.w : undefined,
            height: indicator.h > 0 ? indicator.h : undefined,
          }}
          aria-hidden
        />
        {options.map((opt, i) => {
          const active = opt.value === value;
          return (
            <button
              key={opt.value}
              type="button"
              ref={(el) => {
                optionRefs.current[i] = el;
              }}
              role="tab"
              aria-selected={active}
              disabled={opt.disabled}
              className={`${styles.option} ${active ? styles.optionActive : ""}`}
              onClick={() => onChange(opt.value)}
            >
              {opt.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
