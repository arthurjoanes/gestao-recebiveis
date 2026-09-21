import { Icon } from "./ui";

export function Brand() {
  return (
    <div className="brand">
      <span className="brand-icon" aria-hidden="true">
        <Icon name="titles" />
      </span>
      <span>
        Gestão<span className="brand-light"> de recebíveis</span>
      </span>
    </div>
  );
}
