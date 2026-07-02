const API = "/api";

export async function searchEnterprises(q: string) {
  const r = await fetch(`${API}/search?q=${encodeURIComponent(q)}`);
  if (!r.ok) throw new Error("Recherche echouee");
  return r.json();
}

export async function getEnterprise(bce: string, year?: number) {
  const url = year
    ? `${API}/enterprise/${bce}?year=${year}`
    : `${API}/enterprise/${bce}`;
  const r = await fetch(url);
  if (!r.ok) throw new Error("Entreprise introuvable");
  return r.json();
}

export function statutsEventSource(bce: string): EventSource {
  return new EventSource(`${API}/enterprise/${bce}/statuts/stream`);
}
