// Runnable check: node lib/citations.check.mjs
import assert from "node:assert/strict";
import { bestSupportingLine, linkCitations } from "./citations.ts";

const sources = [
  { documentName: "api_spec.md", page: 1 },
  { documentName: "Pricing.xlsx", page: 2 },
];
assert.equal(linkCitations("600 req/min (api_spec.md, p. 1).", sources), "600 req/min [1](#cite-1).");
assert.equal(linkCitations("$27.90 (pricing.xlsx, page 2)", sources), "$27.90 [2](#cite-2)");
// wrong page, or a document that was never retrieved, stays plain text
assert.equal(linkCitations("x (api_spec.md, p. 9)", sources), "x (api_spec.md, p. 9)");
assert.equal(linkCitations("x (ghost.pdf, p. 1)", sources), "x (ghost.pdf, p. 1)");
assert.equal(linkCitations("no citations (see above)", sources), "no citations (see above)");
const lines = ["# Atlas Sync", "Version 3.2.1 was released in March.", "The default rate limit for Atlas Sync is 600 requests per minute per API key.", "Retention is 14 days."];
assert.equal(bestSupportingLine(lines, ["The default rate limit for Atlas Sync is 600 requests per minute"]), 2);
assert.equal(bestSupportingLine(lines, ["nothing in common"]), -1);
console.log("citations ok");
