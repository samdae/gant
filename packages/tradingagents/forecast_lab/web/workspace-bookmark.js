// URL fragments are browser-side. Preserve the legacy section and bounded filters.
const original = new URLSearchParams(location.search);
const filters = new URLSearchParams();
const market = original.get("market");
if (market === "kr" || market === "us") filters.set("market", market);
for (const name of ["from_date", "to_date"]) {
  const value = original.get(name);
  if (/^\d{4}-\d{2}-\d{2}$/.test(value || "")) filters.set(name, value);
}
const id = original.get("case");
const selected = /^[1-9]\d{0,15}$/.test(id || "") ? "/research/" + id : "/research";
const path = ({ "#results": "/results", "#observe": "/observe" })[location.hash] || selected;
location.replace("/#" + path + (filters.size ? "?" + filters : ""));
