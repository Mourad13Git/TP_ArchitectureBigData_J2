import { configureStore, createSlice, PayloadAction } from "@reduxjs/toolkit";

export interface SearchHit {
  enterprise_number: string;
  name: string;
  status?: string;
}

interface AppState {
  query: string;
  results: SearchHit[];
  loading: boolean;
}

const initialState: AppState = { query: "", results: [], loading: false };

const appSlice = createSlice({
  name: "app",
  initialState,
  reducers: {
    setQuery(state, action: PayloadAction<string>) {
      state.query = action.payload;
    },
    setResults(state, action: PayloadAction<SearchHit[]>) {
      state.results = action.payload;
    },
    setLoading(state, action: PayloadAction<boolean>) {
      state.loading = action.payload;
    },
  },
});

export const { setQuery, setResults, setLoading } = appSlice.actions;
export const store = configureStore({ reducer: { app: appSlice.reducer } });
export type RootState = ReturnType<typeof store.getState>;
