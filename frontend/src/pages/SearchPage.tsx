import { Link } from "react-router-dom";
import { useEffect, useState } from "react";
import { bceToUrl, searchEnterprises } from "../api/client";
import { formatEuro } from "../utils/format";

interface Hit {
  enterprise_number: string;
  name: string;
  status?: string;
  has_gold?: boolean;
  latest_ca?: number;
  years_count?: number;
}

export default function SearchPage() {
  const [input, setInput] = useState("hotel");
  const [results, setResults] = useState<Hit[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (input.length < 2) {
      setResults([]);
      return;
    }
    const t = setTimeout(async () => {
      setLoading(true);
      try {
        setResults(await searchEnterprises(input));
      } catch {
        setResults([]);
      } finally {
        setLoading(false);
      }
    }, 300);
    return () => clearTimeout(t);
  }, [input]);

  return (
    <div className="app">
      <header className="topbar">
        <div className="topbar-inner">
          <h1>BCE Hôtellerie</h1>
          <p className="subtitle">Recherche Silver + ratios Gold (NBB)</p>
        </div>
      </header>

      <main className="page">
        <div className="search-hero">
          <input
            className="search-input"
            placeholder="Nom, numéro BCE, ville..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            autoFocus
          />
          {loading && <p className="muted">Recherche en cours...</p>}
        </div>

        <ul className="results">
          {results.map((r) => (
            <li key={r.enterprise_number}>
              <Link to={`/enterprise/${bceToUrl(r.enterprise_number)}`} className="result-card">
                <div className="result-main">
                  <strong>{r.name}</strong>
                  <span className="bce">{r.enterprise_number}</span>
                </div>
                <div className="result-meta">
                  {r.status && <span className="badge badge-status">{r.status}</span>}
                  {r.has_gold ? (
                    <>
                      <span className="badge badge-gold">Finances NBB</span>
                      <span className="ca-hint">CA {formatEuro(r.latest_ca)}</span>
                      <span className="muted">{r.years_count} exercice(s)</span>
                    </>
                  ) : (
                    <span className="badge badge-muted">Pas de dépôts NBB</span>
                  )}
                </div>
              </Link>
            </li>
          ))}
        </ul>

        {!loading && input.length >= 2 && results.length === 0 && (
          <p className="empty">Aucun résultat pour « {input} »</p>
        )}
      </main>
    </div>
  );
}
