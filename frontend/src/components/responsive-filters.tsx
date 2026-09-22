"use client";
import { useState, type ReactNode } from "react";

/** Keep the applied scope visible while freeing the small-screen result area. */
export function ResponsiveFilters({
  id,
  label,
  scope,
  children,
}: {
  id: string;
  label: string;
  scope: string;
  children: (onApplied: () => void) => ReactNode;
}) {
  const [expanded, setExpanded] = useState(false);
  function applied() {
    if (window.matchMedia("(max-width: 900px)").matches) {
      setExpanded(false);
      document.getElementById(`${id}-toggle`)?.focus();
    }
  }
  return (
    <div className={`responsive-filters ${expanded ? "is-expanded" : ""}`}>
      <div className="filter-scope">
        <span>Recorte aplicado</span>
        <p>{scope}</p>
        <button
          id={`${id}-toggle`}
          className="button secondary filter-toggle"
          type="button"
          aria-expanded={expanded}
          aria-controls={id}
          onClick={() => setExpanded((value) => !value)}
        >
          {expanded ? "Fechar filtros" : label}
        </button>
      </div>
      <div id={id} className="filter-fields">
        {children(applied)}
      </div>
    </div>
  );
}
