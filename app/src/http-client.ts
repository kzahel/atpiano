import createClient, { type ClientOptions } from "openapi-fetch";

import type { paths } from "./generated/schema.js";

export type AtpianoHttpClient = ReturnType<typeof createAtpianoHttpClient>;

export function createAtpianoHttpClient(
  options: ClientOptions = {},
) {
  return createClient<paths>(options);
}
