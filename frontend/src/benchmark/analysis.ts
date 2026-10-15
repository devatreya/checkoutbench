import { api } from "./domain";

// The server owns release/protocol/checkpoint eligibility and all result metrics.
// Every Results view consumes this same response; no browser-side cohort inference.
export const officialResults = () => api("/research/analysis");
