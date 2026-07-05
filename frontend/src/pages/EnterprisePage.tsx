import Plot from "react-plotly.js";
import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getEnterprise, statutsEventSource } from "../api/client";
import {
  buildSankeyFromYear,
  formatEuro,
  formatFte,
  formatPct,
  YearFinancials,
} from "../utils/format";

function InfoRow({ label, value }: { label: string; value?: string }) {
  return (
    <div className="info-row">
      <span className="info-label">{label}</span>
      <span className="info-value">{value || "—"}</span>
    </div>
  );
}

function KpiCard({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div className={`kpi-card${accent ? " kpi-accent" : ""}`}>
      <span className="kpi-label">{label}</span>
      <span className="kpi-value">{value}</span>
    </div>
  );
}

export default function EnterprisePage() {
  const { bce } = useParams<{ bce: string }>();
  const [data, setData] = useState<any>(null);
  const [year, setYear] = useState<number | null>(null);
  const [statuts, setStatuts] = useState<any[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!bce) return;
    setLoading(true);
    getEnterprise(bce)
      .then((res) => {
        setData(res);
        if (res.gold?.years?.length) {
          setYear(res.gold.years[res.gold.years.length - 1].year);
        }
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [bce]);

  useEffect(() => {
    if (!bce) return;
    setStatuts([]);
    setStreaming(true);
    const es = statutsEventSource(bce);
    es.addEventListener("statut", (ev) => {
      setStatuts((prev) => [...prev, JSON.parse(ev.data)]);
    });
    es.addEventListener("done", () => {
      setStreaming(false);
      es.close();
    });
    es.onerror = () => {
      setStreaming(false);
      es.close();
    };
    return () => es.close();
  }, [bce]);

  const years: YearFinancials[] = data?.gold?.years || [];
  const selectedYear = year ?? years[years.length - 1]?.year;
  const yearData = years.find((y) => y.year === selectedYear);

  const sankey = useMemo(
    () => (yearData ? buildSankeyFromYear(yearData) : null),
    [yearData]
  );

  const name =
    data?.silver?.denominations?.find((d: any) => d.TypeOfDenomination === "1")?.Denomination ||
    data?.silver?.denominations?.[0]?.Denomination ||
    data?.enterprise_number;

  const address = data?.silver?.addresses?.[0];

  if (loading && !data) {
    return (
      <div className="app">
        <main className="page"><p className="loading">Chargement de la fiche...</p></main>
      </div>
    );
  }

  if (error) {
    return (
      <div className="app">
        <main className="page">
          <p className="error">{error}</p>
          <Link to="/" className="back-link">← Retour recherche</Link>
        </main>
      </div>
    );
  }

  return (
    <div className="app">
      <header className="topbar">
        <div className="topbar-inner">
          <Link to="/" className="back-link">← Recherche</Link>
          <h1>{name}</h1>
          <p className="subtitle">{data.enterprise_number}</p>
        </div>
      </header>

      <main className="page page-detail">
        <div className="grid-2">
          <section className="card">
            <h2>Identité</h2>
            <InfoRow label="Statut" value={data.silver.StatusLabel} />
            <InfoRow label="Forme juridique" value={data.silver.JuridicalFormLabel} />
            <InfoRow label="Type" value={data.silver.TypeOfEnterpriseLabel} />
            <InfoRow
              label="Date de création"
              value={data.silver.StartDate}
            />
            <InfoRow
              label="Adresse (siège REGO)"
              value={
                address
                  ? `${address.StreetFR || address.StreetNL || ""} ${address.HouseNumber || ""}, ${address.Zipcode || ""} ${address.MunicipalityFR || address.MunicipalityNL || ""}`.trim()
                  : undefined
              }
            />
          </section>

          <section className="card">
            <h2>Contact</h2>
            {data.contacts?.length ? (
              <ul className="contact-list">
                {data.contacts.map((c: any, i: number) => (
                  <li key={`${c.type}-${i}`} className="contact-item">
                    <span className="info-label">{c.label}</span>
                    {c.type === "WEB" ? (
                      <a
                        href={c.value.startsWith("http") ? c.value : `https://${c.value}`}
                        target="_blank"
                        rel="noreferrer"
                        className="ext-link"
                      >
                        {c.value}
                      </a>
                    ) : c.type === "EMAIL" ? (
                      <a href={`mailto:${c.value}`} className="ext-link">{c.value}</a>
                    ) : (
                      <span className="info-value">{c.value}</span>
                    )}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted">
                Aucun téléphone, e-mail ou site web publié au KBO pour cette entreprise.
              </p>
            )}
          </section>
        </div>

        <section className="card">
          <h2>Activités NACE</h2>
          <ul className="clean-list">
            {(data.silver.activities || []).map((a: any, i: number) => (
              <li key={i}>
                <span className="nace-code">{a.NaceCode}</span>
                <span>{a.NaceLabel}</span>
                <span className="muted">({a.ClassificationLabel})</span>
              </li>
            ))}
          </ul>
        </section>

        <section className="card">
          <h2>Dirigeants</h2>
          {data.dirigeants?.length ? (
            <ul className="clean-list">
              {data.dirigeants.map((d: any, i: number) => (
                <li key={i}><strong>{d.nom}</strong> — {d.role}</li>
              ))}
            </ul>
          ) : (
            <p className="muted">Aucun dirigeant récupéré (kbopub indisponible ou non publié).</p>
          )}
        </section>

        {years.length > 0 && yearData ? (
          <>
            <section className="card card-highlight">
              <div className="section-head">
                <h2>Performance financière</h2>
                <div className="year-tabs">
                  {years.map((y) => (
                    <button
                      key={y.year}
                      type="button"
                      className={`year-tab${y.year === selectedYear ? " active" : ""}`}
                      onClick={() => setYear(y.year)}
                    >
                      {y.year}
                    </button>
                  ))}
                </div>
              </div>

              <div className="kpi-grid">
                <KpiCard label="Chiffre d'affaires" value={formatEuro(yearData.chiffre_affaires)} accent />
                <KpiCard label="Marge brute" value={formatEuro(yearData.ratios?.marge_brute)} />
                <KpiCard label="EBIT" value={formatEuro(yearData.ebit)} />
                <KpiCard label="Résultat net" value={formatEuro(yearData.resultat_net)} accent />
              </div>

              <div className="kpi-grid kpi-grid-secondary">
                <KpiCard label="Effectif (ETP)" value={formatFte(yearData.effectif_fte)} accent />
                <KpiCard label="Trésorerie" value={formatEuro(yearData.tresorerie)} />
                <KpiCard label="Dettes financières" value={formatEuro(yearData.dettes_financieres)} />
                <KpiCard label="Fonds propres" value={formatEuro(yearData.fonds_propres)} />
              </div>

              <div className="kpi-grid kpi-grid-secondary">
                <KpiCard label="Capital souscrit" value={formatEuro(yearData.capital_souscrit)} />
              </div>

              <table className="ratios">
                <thead>
                  <tr><th>Ratio</th><th>Valeur</th></tr>
                </thead>
                <tbody>
                  <tr><td>CA / ETP</td><td>{formatEuro(yearData.ratios?.ca_par_etp)}</td></tr>
                  <tr><td>Marge nette</td><td>{formatPct(yearData.ratios?.marge_nette_pct)}</td></tr>
                  <tr><td>ROE</td><td>{formatPct(yearData.ratios?.roe_pct)}</td></tr>
                  <tr><td>Ratio de liquidité</td><td>{yearData.ratios?.ratio_liquidite ?? "—"}</td></tr>
                  <tr><td>Taux d'endettement</td><td>{formatPct(yearData.ratios?.taux_endettement_pct)}</td></tr>
                </tbody>
              </table>
            </section>

            {sankey && (
              <section className="card">
                <h2>Sankey — compte de résultats ({sankey.year})</h2>
                <Plot
                  data={[{
                    type: "sankey",
                    orientation: "h",
                    node: {
                      pad: 20,
                      thickness: 24,
                      label: sankey.nodes.map((n) => `${n.label}\n${formatEuro(n.value)}`),
                      color: ["#4a6cf7", "#22c55e", "#0ea5e9"],
                    },
                    link: {
                      source: sankey.links.map((l) => l.source),
                      target: sankey.links.map((l) => l.target),
                      value: sankey.links.map((l) => l.value),
                      color: "rgba(74,108,247,0.35)",
                    },
                  }]}
                  layout={{
                    height: 300,
                    margin: { l: 20, r: 20, t: 10, b: 10 },
                    paper_bgcolor: "rgba(0,0,0,0)",
                    font: { family: "system-ui, sans-serif", size: 12 },
                  }}
                  config={{ displayModeBar: false, responsive: true }}
                  style={{ width: "100%" }}
                />
              </section>
            )}
          </>
        ) : (
          <section className="card card-warning">
            <h2>Données financières indisponibles</h2>
            <p>
              Aucun dépôt NBB n'est présent dans <code>hotel_gold</code> pour cette entreprise.
              Les ratios (CA, EBIT, etc.) apparaissent uniquement après scraping NBB et passage Gold.
            </p>
            <p className="muted">
              Essayez <strong>Hotel Demo Bruxelles</strong> (0339.226.816) pour voir une fiche complète avec finances.
            </p>
          </section>
        )}

        <section className="card">
          <h2>
            Publications eJustice
            <span className="muted section-hint">Moniteur belge</span>
          </h2>
          {data.ejustice_liste_url && (
            <p className="muted">
              <a href={data.ejustice_liste_url} target="_blank" rel="noreferrer" className="ext-link">
                Voir toutes les publications sur ejustice.just.fgov.be →
              </a>
            </p>
          )}
          {data.ejustice_publications?.length ? (
            <ul className="ejustice-list">
              {data.ejustice_publications.map((pub: any) => (
                <li key={pub.id} className="ejustice-item">
                  <div className="ejustice-head">
                    <strong>{pub.titre}</strong>
                    <span className="muted">{pub.date}</span>
                  </div>
                  <span className="muted">Réf. {pub.reference}</span>
                  {pub.pdf_url && (
                    <a href={pub.pdf_url} target="_blank" rel="noreferrer" className="ext-link">
                      PDF Moniteur →
                    </a>
                  )}
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">Aucune publication eJustice trouvée pour cette entreprise.</p>
          )}
        </section>

        <section className="card">
          <h2>
            Statuts & actes publiés
            {streaming && <span className="spinner" aria-label="Chargement">⟳</span>}
          </h2>
          <p className="muted section-hint-block">
            Actes statutaires repérés au Moniteur belge (eJustice) lorsque statuts.notaire.be est inaccessible.
          </p>
          {statuts.length === 0 && !streaming && (
            <p className="muted">Aucun acte statutaire trouvé pour cette entreprise.</p>
          )}
          <ul className="statuts-list">
            {statuts.map((s) => (
              <li key={s.id} className="statut-item">
                <div className="ejustice-head">
                  <strong>{s.titre}</strong>
                  <span className="muted">{s.date}</span>
                </div>
                <p>{s.resume}</p>
                {s.pdf_url && (
                  <a href={s.pdf_url} target="_blank" rel="noreferrer" className="ext-link">
                    PDF Moniteur →
                  </a>
                )}
              </li>
            ))}
          </ul>
        </section>
      </main>
    </div>
  );
}
