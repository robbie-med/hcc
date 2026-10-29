// Smoke test for index.html search and RAF logic against the real data.json, no browser needed.
// Run: node build/check.mjs
import { readFileSync } from "node:fs";
import assert from "node:assert/strict";

const file = p => readFileSync(new URL(p, import.meta.url), "utf8");
const html = file("../index.html");
const js = html.slice(html.indexOf("<script>") + 8, html.lastIndexOf("</script>"));

const els = {}, docH = {};
const el = id => els[id] ??= { value: "", innerHTML: "", textContent: "", hidden: false, dataset: {}, h: {},
  style: { setProperty() {}, removeProperty() {} }, classList: { toggle() {} }, addEventListener(t, f) { (this.h[t] ??= []).push(f); }, setAttribute() {}, select() {}, focus() {} };
globalThis.matchMedia = () => ({ matches: false, addEventListener() {} });
globalThis.document = { documentElement: el("root"), getElementById: el, querySelectorAll: () => [], addEventListener: (t, f) => (docH[t] ??= []).push(f) };
globalThis.getComputedStyle = () => ({ getPropertyValue: () => "#0a6b70" });
globalThis.localStorage = { getItem: () => null, setItem() {} };
globalThis.window = { scrollTo() {} };
globalThis.fetch = async () => ({ ok: true, json: async () => JSON.parse(file("../data.json")) });

const wait = ms => new Promise(r => setTimeout(r, ms));
new Function(js)();
while (!el("src").textContent) await wait(50);

async function search(q) { el("q").value = q; el("q").h.input.forEach(f => f()); await wait(150); return el("out").innerHTML; }
const add = c => docH.click[0]({ target: { closest: () => ({ dataset: { add: c }, classList: { contains: () => false } }) } });

let out = await search("diabetis");
assert.match(out, /Showing results for <b>diabetes<\/b>/);
assert.match(out, /E11\./);
out = await search("copd exacerbaton");
assert.match(out, /J44\.1/);
out = await search("chf");
assert.doesNotMatch(out, /Showing results for/);
assert.match(out, /I50\./);
out = await search("heart fail");  // partial word is a prefix, not a typo
assert.doesNotMatch(out, /Showing results for/);
assert.match(out, /I50\./);
out = await search("E11.2");
assert.match(out, /E11\.22/);

// E11.9 (HCC 38) is outranked by E11.22 (HCC 37): 0.166 + I50.22 (HCC 226) 0.360
["E1122", "E119", "I5022"].forEach(add);
assert.equal(el("tcount").textContent, "3 selected, RAF 0.526");
assert.match(el("tlist").innerHTML, /<s>HCC 38<\/s> outranked/);

console.log("ok");
