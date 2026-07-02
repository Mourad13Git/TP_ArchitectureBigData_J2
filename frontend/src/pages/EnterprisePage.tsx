import Plot from "react-plotly.js";
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { getEnterprise, statutsEventSource } from "../api/client";

export default function EnterprisePage() {
  const { bce } = useParams<{ bce: string }>();
  const [data, setData] = useState<any>(null);
  const [year, setYear] = useState<number | null>(null);
  const [statuts, setStatuts] = useState<any[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!bce) return;
    getEnterprise(bce, year ?? undefined)
      .then(setData)
      .catch((e) => setError(e.message));
  }, [bce, year]);

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
    es.addEventListener("warning", (ev) => {
      console.warn(JSON.parse(ev.data));
    });
    es.onerror = () => {
      setStreaming(false);
      es.close();
    };
    return () => es.close();
  }, [bce]);

  if (error) return <p className="error">{error}</p>;
  if (!data) return <p>Chargement...</p>;

  const years: any[] = data.gold?.years || [];
  const selectedYear = year ?? years[years.length - 1]?.year;
  const yearData = years.find((y) => y.year === selectedYear);
  const sankey = data.sankey;

  return (
    <div className="page">
      <h1>{data.silver.denominations?.[0]?.Denomination || bce}</h1>
      <p className="muted">{data.enterprise_number}</p>

      <section>
        <h2>Informations générales</h2>
        <p>Statut : {data.silver.StatusLabel}</p>
        <p>Forme : {data.silver.JuridicalFormLabel}</p>
        <p>Adresse : {data.silver.addresses?.[0]?.StreetFR} {data.silver.addresses?.[0]?.HouseNumber}, {data.silver.addresses?.[0]?.Zipcode} {data.silver.addresses?.[0]?.MunicipalityFR}</p>
      </section>

      <section>
        <h2>Activités NACE</h2>
        <ul>
          {(data.silver.activities || []).slice(0, 5).map((a: any, i: number) => (
            <li key={i}>{a.NaceCode} — {a.NaceLabel} ({a.ClassificationLabel})</li>
          ))}
        </ul>
      </section>

      <section>
        <h2>Dirigeants</h2>
        <ul>
          {data.dirigeants.map((d: any, i: number) => (
            <li key={i}>{d.nom} — {d.role}</li>
          ))}
        </ul>
      </section>

      {years.length > 0 && (
        <section>
          <h2>Ratios financiers</h2>
          <label>
            Exercice :
            <select value={selectedYear} onChange={(e) => setYear(Number(e.target.value))}>
              {years.map((y) => (
                <option key={y.year} value={y.year}>{y.year}</option>
              ))}
            </select>
          </label>
          {yearData && (
            <table className="ratios">
              <thead>
                <tr><th>Indicateur</th><th>Valeur</th></tr>
              </thead>
              <tbody>
                <tr><td>Chiffre d'affaires</td><td>{yearData.chiffre_affaires?.toLocaleString("fr-BE")} €</td></tr>
                <tr><td>Marge brute</td><td>{yearData.ratios?.marge_brute?.toLocaleString("fr-BE")} €</td></tr>
                <tr><td>EBIT</td><td>{yearData.ebit?.toLocaleString("fr-BE")} €</td></tr>
                <tr><td>Résultat net</td><td>{yearData.resultat_net?.toLocaleString("fr-BE")} €</td></tr>
                <tr><td>Marge nette %</td><td>{yearData.ratios?.marge_nette_pct} %</td></tr>
                <tr><td>ROE %</td><td>{yearData.ratios?.roe_pct} %</td></tr>
                <tr><td>Liquidité</td><td>{yearData.ratios?.ratio_liquidite}</td></tr>
                <tr><td>Endettement %</td><td>{yearData.ratios?.taux_endettement_pct} %</td></tr>
              </tbody>
            </table>
          )}
        </section>
      )}

      {sankey && (
        <section>
          <h2>Sankey — compte de résultats ({sankey.year})</h2>
          <Plot
            data={[{
              type: "sankey",
              orientation: "h",
              node: {
                pad: 15,
                thickness: 20,
                label: sankey.nodes.map((n: any) => n.label),
              },
              link: {
                source: sankey.links.map((l: any) => l.source),
                target: sankey.links.map((l: any) => l.target),
                value: sankey.links.map((l: any) => l.value),
              },
            }]}
            layout={{ height: 320, margin: { l: 20, r: 20, t: 20, b: 20 } }}
            style={{ width: "100%" }}
          />
        </section>
      )}

      <section>
        <h2>Statuts notaire {streaming && <span className="spinner">⏳</span>}</h2>
        <ul>
          {statuts.map((s) => (
            <li key={s.id}><strong>{s.titre}</strong> — {s.date}<br />{s.resume}</li>
          ))}
        </ul>
      </section>
    </div>
  );
}
