export const state = { hits: 0, limit: 2 };
export function createClient(url, key) {
  return {
    auth: { getUser: async (t) => t === "good" ? { data: { user: { id: "u1" } }, error: null } : { data: { user: null }, error: { message: "bad" } } },
    rpc: async (name, args) => { state.hits++; state.last = args; return state.hits > state.limit ? { error: { message: "rate_limited" } } : { error: null }; },
  };
}
