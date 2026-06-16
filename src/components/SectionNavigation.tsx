import type { PackSection } from "../types/pack";

export interface SectionNavigationProps {
  sections: PackSection[];
  activeSection: number;
  onSelect: (section: number) => void;
}

export function SectionNavigation({ sections, activeSection, onSelect }: SectionNavigationProps) {
  return (
    <div aria-label="Section 导航" className="section-nav" role="tablist">
      {sections.map((section) => {
        const label = String(section.number).padStart(2, "0");
        const active = section.number === activeSection;
        return (
          <button
            aria-selected={active}
            className="section-tab"
            data-active={active ? "true" : "false"}
            key={section.number}
            onClick={() => onSelect(section.number)}
            role="tab"
            type="button"
          >
            {label}
          </button>
        );
      })}
    </div>
  );
}

export default SectionNavigation;
