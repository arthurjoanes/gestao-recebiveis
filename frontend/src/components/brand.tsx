import { Icon } from "./ui";

export function Brand() {
  return (
    <div className="brand">
      <span className="brand-icon" aria-hidden="true">
        <Icon name="titles" />
      </span>
      <span>
        Recebíveis<small>Gestão da carteira</small>
      </span>
    </div>
  );
}
