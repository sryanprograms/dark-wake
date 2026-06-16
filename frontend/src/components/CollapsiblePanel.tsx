import { useEffect, useState, type ReactNode } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";

type CollapsiblePanelProps = {
  title: string;
  icon?: ReactNode;
  count?: number | string;
  headerActions?: ReactNode;
  className?: string;
  defaultCollapsed?: boolean;
  collapsed?: boolean;
  onCollapsedChange?: (collapsed: boolean) => void;
  /** Which screen edge the panel sits on — controls chevron direction. */
  edge?: "left" | "right";
  children: ReactNode;
};

export function CollapsiblePanel({
  title,
  icon,
  count,
  headerActions,
  className,
  defaultCollapsed = false,
  collapsed: collapsedProp,
  onCollapsedChange,
  edge = "left",
  children,
}: CollapsiblePanelProps) {
  const [internalCollapsed, setInternalCollapsed] = useState(defaultCollapsed);
  const collapsed = collapsedProp ?? internalCollapsed;

  useEffect(() => {
    if (collapsedProp == null) {
      setInternalCollapsed(defaultCollapsed);
    }
  }, [defaultCollapsed, collapsedProp]);

  const setCollapsed = (next: boolean) => {
    if (collapsedProp == null) setInternalCollapsed(next);
    onCollapsedChange?.(next);
  };

  const CollapseIcon = edge === "left" ? ChevronLeft : ChevronRight;
  const ExpandIcon = edge === "left" ? ChevronRight : ChevronLeft;

  return (
    <aside
      className={[
        "hud-panel",
        "collapsible-panel",
        collapsed ? "collapsible-panel--collapsed" : "",
        className ?? "",
      ]
        .filter(Boolean)
        .join(" ")}
    >
      <div className="hud-panel__header collapsible-panel__header">
        {icon}
        <span className="collapsible-panel__title">{title}</span>
        {!collapsed && count != null && <span className="hud-panel__count">{count}</span>}
        {!collapsed && headerActions}
        <button
          type="button"
          className="collapsible-panel__toggle"
          onClick={() => setCollapsed(!collapsed)}
          aria-expanded={!collapsed}
          aria-label={collapsed ? `Expand ${title}` : `Collapse ${title}`}
          title={collapsed ? "Expand panel" : "Collapse panel"}
        >
          {collapsed ? (
            <>
              {count != null && <span className="collapsible-panel__collapsed-count">{count}</span>}
              <ExpandIcon size={14} />
            </>
          ) : (
            <CollapseIcon size={14} />
          )}
        </button>
      </div>
      {!collapsed && <div className="collapsible-panel__body">{children}</div>}
    </aside>
  );
}
