import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

import { Ajv2020 } from "ajv/dist/2020.js";

interface FixtureObject {
  readonly model: string;
  readonly value: Record<string, unknown>;
}

interface FixtureDocument {
  readonly schema_version: string;
  readonly objects: readonly FixtureObject[];
}

const repositoryRoot = fileURLToPath(new URL("../..", import.meta.url));
const openapi = JSON.parse(
  readFileSync(
    `${repositoryRoot}/contracts/openapi/atpiano-product-v1.json`,
    "utf8",
  ),
) as Record<string, unknown>;
const fixtures = JSON.parse(
  readFileSync(
    `${repositoryRoot}/contracts/fixtures/v1/product-examples.json`,
    "utf8",
  ),
) as FixtureDocument;

function validatorFor(model: string) {
  const ajv = new Ajv2020({
    allErrors: true,
    formats: { "date-time": true },
    strict: false,
  });
  return ajv.compile({
    ...openapi,
    $ref: `#/components/schemas/${model}`,
  });
}

test("shared product examples validate in TypeScript", () => {
  assert.equal(fixtures.schema_version, "atpiano.product-examples.v1");
  assert.ok(fixtures.objects.length >= 15);
  for (const fixture of fixtures.objects) {
    const validate = validatorFor(fixture.model);
    assert.equal(
      validate(fixture.value),
      true,
      `${fixture.model}: ${JSON.stringify(validate.errors)}`,
    );
  }
});

test("incompatible schema versions fail in TypeScript", () => {
  const workspace = fixtures.objects.find(
    (fixture) => fixture.model === "Workspace",
  );
  assert.ok(workspace);
  const validate = validatorFor("Workspace");
  assert.equal(
    validate({ ...workspace.value, schema_version: "atpiano.product.v2" }),
    false,
  );
});
