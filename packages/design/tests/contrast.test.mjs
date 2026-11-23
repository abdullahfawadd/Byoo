import assert from "node:assert/strict";
import test from "node:test";
import { light, dark } from "../src/index.ts";

function luminance(hex) {
  const values = hex.match(/[\da-f]{2}/gi).map((x) => parseInt(x, 16) / 255);
  const linear = values.map((x) => x <= 0.04045 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4);
  return linear[0] * 0.2126 + linear[1] * 0.7152 + linear[2] * 0.0722;
}
function contrast(a, b) {
  const x = luminance(a), y = luminance(b);
  return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05);
}
for (const [name, colors] of Object.entries({ light, dark })) {
  test(`${name} design token pairings meet AA normal text contrast`, () => {
    for (const [a, b] of [["text","background"],["text","surface"],["muted","surface"],["muted","background"],["onPrimary","primary"],["accentInk","coral"],["accentInk","citrus"]]) {
      assert.ok(contrast(colors[a], colors[b]) >= 4.5, `${a}/${b} = ${contrast(colors[a], colors[b]).toFixed(2)}`);
    }
  });
}
