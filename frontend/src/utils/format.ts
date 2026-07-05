export interface SearchHit {
  enterprise_number: string;
  name: string;
  status?: string;
  has_gold?: boolean;
  latest_ca?: number | null;
  years_count?: number;
}

export interface YearFinancials {
  year: number;
  chiffre_affaires?: number;
  achats?: number;
  variation_stocks?: number;
  ebit?: number;
  resultat_net?: number;
  tresorerie?: number;
  dettes_financieres?: number;
  fonds_propres?: number;
  capital_souscrit?: number;
  effectif_fte?: number;
  ratios?: {
    marge_brute?: number;
    marge_nette_pct?: number;
    roe_pct?: number;
    ratio_liquidite?: number;
    taux_endettement_pct?: number;
    ca_par_etp?: number;
  };
}

export function bceToUrl(bce: string): string {
  return bce.replace(/\./g, "");
}

export function formatEuro(value?: number | null): string {
  if (value === undefined || value === null || Number.isNaN(value)) return "—";
  return new Intl.NumberFormat("fr-BE", {
    style: "currency",
    currency: "EUR",
    maximumFractionDigits: 0,
  }).format(value);
}

export function formatPct(value?: number | null): string {
  if (value === undefined || value === null || Number.isNaN(value)) return "—";
  return `${value.toLocaleString("fr-BE", { maximumFractionDigits: 2 })} %`;
}

export function formatFte(value?: number | null): string {
  if (value === undefined || value === null || Number.isNaN(value)) return "—";
  return `${value.toLocaleString("fr-BE", { maximumFractionDigits: 1 })} ETP`;
}

export function buildSankeyFromYear(yearData: YearFinancials) {
  const ca = yearData.chiffre_affaires ?? 0;
  const achats = yearData.achats ?? 0;
  const varStocks = yearData.variation_stocks ?? 0;
  const rn = yearData.resultat_net ?? 0;
  const margeBrute = yearData.ratios?.marge_brute ?? ca - achats + varStocks;
  return {
    year: yearData.year,
    nodes: [
      { label: "CA", value: ca },
      { label: "Marge brute", value: Math.max(margeBrute, 0) },
      { label: "Résultat net", value: rn },
    ],
    links: [
      { source: 0, target: 1, value: Math.max(margeBrute, 0) },
      { source: 1, target: 2, value: Math.max(rn, 0) },
    ],
  };
}
