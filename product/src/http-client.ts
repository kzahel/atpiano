import createClient, { type ClientOptions } from "openapi-fetch";

import type { paths } from "./generated/schema.js";

export type ProductHttpClient = ReturnType<typeof createProductHttpClient>;

export function createProductHttpClient(
  options: ClientOptions = {},
) {
  return createClient<paths>(options);
}
