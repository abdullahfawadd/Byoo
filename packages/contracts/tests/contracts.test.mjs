import assert from "node:assert/strict";
import test from "node:test";
import { estimateOrder, sectors } from "../src/index.ts";

test("Appendix D rice basket uses one flat fee in paisa", () => {
  assert.deepEqual(estimateOrder(2, 245000, 209000), {
    wholesaleSubtotal: 418000, platformFee: 4000, totalPayable: 422000,
    retailTotal: 490000, grossSavings: 72000, netSavings: 68000,
  });
});
test("all approved sectors carry valid Islamabad display coordinates", () => {
  assert.equal(sectors.length, 9);
  assert.equal(new Set(sectors.map(({ id }) => id)).size, sectors.length);
  for (const { lat, lng } of sectors) {
    assert.ok(lat >= 33.64 && lat <= 33.74);
    assert.ok(lng >= 72.96 && lng <= 73.12);
  }
});
