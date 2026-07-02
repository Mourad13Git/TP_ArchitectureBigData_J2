import { useDispatch, useSelector } from "react-redux";
import { Link } from "react-router-dom";
import { useEffect, useState } from "react";
import { searchEnterprises } from "../api/client";
import { RootState, setLoading, setQuery, setResults } from "../store";

export default function SearchPage() {
  const dispatch = useDispatch();
  const { query, results, loading } = useSelector((s: RootState) => s.app);
  const [input, setInput] = useState(query);

  useEffect(() => {
    if (input.length < 2) {
      dispatch(setResults([]));
      return;
    }
    const t = setTimeout(async () => {
      dispatch(setLoading(true));
      dispatch(setQuery(input));
      try {
        const data = await searchEnterprises(input);
        dispatch(setResults(data));
      } catch {
        dispatch(setResults([]));
      } finally {
        dispatch(setLoading(false));
      }
    }, 300);
    return () => clearTimeout(t);
  }, [input, dispatch]);

  return (
    <div className="page">
      <h1>BCE — Secteur hôtelier</h1>
      <input
        className="search-input"
        placeholder="Nom ou numéro BCE..."
        value={input}
        onChange={(e) => setInput(e.target.value)}
      />
      {loading && <p className="muted">Recherche...</p>}
      <ul className="results">
        {results.map((r) => (
          <li key={r.enterprise_number}>
            <Link to={`/enterprise/${r.enterprise_number}`}>
              <strong>{r.name}</strong>
              <span>{r.enterprise_number}</span>
              {r.status && <em>{r.status}</em>}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
