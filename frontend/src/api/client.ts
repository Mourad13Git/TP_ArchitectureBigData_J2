const API = "/api";

export async function searchEnterprises(q: string) {
  const r = await fetch(`${API}/search?q=${encodeURIComponent(q)}`);
  if (!r.ok) throw new Error("Recherche echouee");
  return r.json();
}

/** BCE sans points dans l'URL (evite les bugs de routage avec les dots). */
export function bceToUrl(bce: string): string {
  return bce.replace(/\./g, "");
}

export async function getEnterprise(bceUrl: string, year?: number) {
  const url = year
    ? `${API}/enterprise/${bceUrl}?year=${year}`
    : `${API}/enterprise/${bceUrl}`;
  const r = await fetch(url);
  if (!r.ok) throw new Error("Entreprise introuvable");
  return r.json();
}

export function statutsEventSource(bceUrl: string): EventSource {
  return new EventSource(`${API}/enterprise/${bceUrl}/statuts/stream`);
}
