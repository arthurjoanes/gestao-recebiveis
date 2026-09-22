"use client";
import { useState } from "react";
import { api, errorMessage } from "@/lib/api";
import type { Session } from "@/lib/types";
import { Alert, Icon } from "@/components/ui";
import { Brand } from "@/components/brand";

export function Login({
  notice,
  onLogin,
}: {
  notice: string;
  onLogin: (session: Session) => void;
}) {
  const [email, setEmail] = useState("operador@example.com");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit() {
    setBusy(true);
    setError("");
    try {
      onLogin(
        await api<Session>("/auth/login", {
          method: "POST",
          body: JSON.stringify({ email, password }),
        }),
      );
    } catch (failure) {
      setError(errorMessage(failure));
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="login-page">
      <div className="login-brand">
        <Brand />
      </div>
      <div className="login-grid">
        <section className="login-intro" aria-label="Sobre a carteira">
          <p className="eyebrow">CONTAS A RECEBER</p>
          <h2>
            Do arquivo à baixa,
            <br />
            cada título tem um histórico.
          </h2>
          <ol>
            <li>
              <span>01</span>
              <div>
                <strong>Confira antes de importar</strong>
                <p>A prévia mostra linhas novas, repetições e conflitos.</p>
              </div>
            </li>
            <li>
              <span>02</span>
              <div>
                <strong>Acompanhe o vencimento</strong>
                <p>Separe o saldo em aberto dos pagamentos recebidos.</p>
              </div>
            </li>
            <li>
              <span>03</span>
              <div>
                <strong>Registre o pagamento</strong>
                <p>
                  A baixa integral preserva o registro e encerra lembretes
                  pendentes.
                </p>
              </div>
            </li>
          </ol>
          <p className="footnote">
            Demonstração com dados fictícios e envio simulado.
          </p>
        </section>
        <section className="login-card">
          <p className="eyebrow">ACESSO À CARTEIRA</p>
          <h1>Entrar</h1>
          <p>Consulte títulos, confira importações e acompanhe lembretes.</p>

          {notice && <Alert>{notice}</Alert>}
          {error && <Alert>{error}</Alert>}
          <form
            onSubmit={(event) => {
              event.preventDefault();
              void submit();
            }}
          >
            <label>
              E-mail
              <input
                type="email"
                maxLength={254}
                autoComplete="username"
                required
                value={email}
                onChange={(event) => setEmail(event.target.value)}
              />
            </label>
            <label>
              Senha
              <input
                type="password"
                maxLength={200}
                autoComplete="current-password"
                required
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            </label>
            <button className="button" type="submit" disabled={busy}>
              {busy ? "Entrando…" : "Entrar"}
              <Icon name="right" />
            </button>
          </form>
          <details className="demo-credentials" open>
            <summary>Contas de demonstração</summary>
            <p>
              <strong>Operador:</strong> operador@example.com
              <br />
              <strong>Leitor:</strong> leitor@example.com
              <br />
              <strong>Senha:</strong> <code>Recebiveis!2026</code>
            </p>
            <p>
              Disponíveis no modo demo. Operador altera a carteira; leitor
              apenas consulta.
            </p>
            <div className="button-group">
              <button
                className="text-button"
                onClick={() => {
                  setEmail("operador@example.com");
                  setPassword("Recebiveis!2026");
                }}
              >
                Usar operador
              </button>
              <button
                className="text-button"
                onClick={() => {
                  setEmail("leitor@example.com");
                  setPassword("Recebiveis!2026");
                }}
              >
                Usar leitor
              </button>
            </div>
          </details>
        </section>
      </div>
    </main>
  );
}
