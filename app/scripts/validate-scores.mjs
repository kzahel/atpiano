import { mkdir } from "node:fs/promises";
import path from "node:path";
import process from "node:process";

import { chromium, webkit } from "playwright";

const REPORT_SCHEMA = "atpiano.score-browser-validation.v1";
const engines = { chromium, webkit };

class ValidationFailure extends Error {
  constructor(category, stage, message, details = {}) {
    super(message);
    this.category = category;
    this.stage = stage;
    this.details = details;
  }
}

function failure(error) {
  if (error instanceof ValidationFailure) {
    return {
      category: error.category,
      stage: error.stage,
      message: error.message,
      details: error.details,
    };
  }
  return {
    category: "browser-runtime",
    stage: "browser",
    message: error instanceof Error ? error.message : String(error),
    details: {},
  };
}

async function stdinJson() {
  const chunks = [];
  for await (const chunk of process.stdin) chunks.push(chunk);
  return JSON.parse(Buffer.concat(chunks).toString("utf8"));
}

async function visibleCursor(page, timeout) {
  await page.locator("#cursorImg-0").waitFor({
    state: "visible",
    timeout,
  });
}

function cursorSeekSample(target, attackSample) {
  const step = Math.max(1, Math.round(target.sample_rate_hz / 100));
  const maximum = Math.min(
    target.source_frame_count,
    target.source_horizon_sample,
  );
  const seekSample = Math.min(maximum, Math.ceil(attackSample / step) * step);
  if (seekSample < attackSample) {
    throw new Error(
      `No legal playback seek sample at or after mapped attack ${attackSample}`,
    );
  }
  return seekSample;
}

async function seek(page, sample, timeout) {
  const scrubber = page.getByRole("slider", {
    name: "Recorded audio position",
  });
  await scrubber.waitFor({ state: "visible", timeout });
  await page.waitForFunction(
    () => {
      const input = document.querySelector(
        ".playback-scrubber input[type=range]",
      );
      return input instanceof HTMLInputElement && !input.disabled;
    },
    undefined,
    { timeout },
  );
  await scrubber.evaluate((element, value) => {
    const setter = Object.getOwnPropertyDescriptor(
      HTMLInputElement.prototype,
      "value",
    )?.set;
    if (!setter) throw new Error("HTML input value setter is unavailable");
    setter.call(element, String(value));
    element.dispatchEvent(new Event("input", { bubbles: true }));
    element.dispatchEvent(new Event("change", { bubbles: true }));
  }, sample);
  await visibleCursor(page, timeout);
}

async function requireNoScoreErrors(page, stage) {
  const errors = page.locator([
    ".score-render-error",
    ".reader-advisory",
    ".reader-loading[role='alert']",
    ".client-update-notice.urgent",
  ].join(", "));
  const messages = await errors.allTextContents();
  if (messages.length > 0) {
    throw new ValidationFailure(
      stage === "reader" ? "reader-render" : "inline-render",
      stage,
      messages.join(" | "),
    );
  }
}

async function selectedSession(page, sessionId) {
  return page.evaluate(async (expected) => {
    const response = await fetch(
      `/api/v1/workspaces/local/sessions/${encodeURIComponent(expected)}`,
      { headers: { Accept: "application/json" } },
    );
    if (!response.ok) return null;
    return (await response.json()).session_id ?? null;
  }, sessionId);
}

async function exerciseReader(page, target, timeout) {
  const expectedPlaybackSample = cursorSeekSample(
    target,
    target.cursor_samples[0],
  );
  await seek(page, expectedPlaybackSample, timeout);
  await page.getByRole("button", { name: "Open score reader" }).click();
  const reader = page.locator(".score-reader");
  await reader.waitFor({ state: "visible", timeout });
  await page.locator(".reader-score-paper svg").first().waitFor({
    state: "visible",
    timeout,
  });
  await requireNoScoreErrors(page, "reader");

  const pages = page.locator(".reader-score-paper .score-render-page");
  const pageCount = await pages.count();
  if (pageCount < 1) {
    throw new ValidationFailure(
      "reader-render",
      "reader",
      "score reader created no OSMD pages",
    );
  }
  for (let index = 0; index < pageCount; index += 1) {
    if (await pages.nth(index).locator("svg").count() < 1) {
      throw new ValidationFailure(
        "reader-render",
        "reader-pages",
        `score reader page ${index + 1} contains no SVG`,
      );
    }
  }
  const label = page.locator(".reader-toolbar output");
  const firstLabel = (await label.textContent()) ?? "";
  if (!/^Page(s)? 1(?:–\d+)? of \d+$/.test(firstLabel)) {
    throw new ValidationFailure(
      "reader-render",
      "reader-navigation",
      `score reader did not start at its first page: ${firstLabel}`,
    );
  }

  const next = page.getByRole("button", { name: "Next score page" });
  let nextLabel = firstLabel;
  if (await next.isEnabled()) {
    await next.click();
    await page.waitForFunction(
      (prior) => document.querySelector(".reader-toolbar output")?.textContent !== prior,
      firstLabel,
      { timeout },
    );
    nextLabel = (await label.textContent()) ?? "";
  }
  let turns = 0;
  while (await next.isEnabled()) {
    const prior = (await label.textContent()) ?? "";
    await next.click();
    await page.waitForFunction(
      (priorLabel) =>
        document.querySelector(".reader-toolbar output")?.textContent !==
          priorLabel,
      prior,
      { timeout },
    );
    turns += 1;
    if (turns > pageCount + 1) {
      throw new ValidationFailure(
        "reader-render",
        "reader-navigation",
        "score reader next-page navigation did not converge",
      );
    }
  }
  const lastLabel = (await label.textContent()) ?? "";
  if (!new RegExp(`of ${pageCount}$`).test(lastLabel)) {
    throw new ValidationFailure(
      "reader-render",
      "reader-navigation",
      `score reader did not reach its last page: ${lastLabel}`,
    );
  }

  const previous = page.getByRole("button", {
    name: "Previous score page",
  });
  turns = 0;
  while (await previous.isEnabled()) {
    const prior = (await label.textContent()) ?? "";
    await previous.click();
    await page.waitForFunction(
      (priorLabel) =>
        document.querySelector(".reader-toolbar output")?.textContent !==
          priorLabel,
      prior,
      { timeout },
    );
    turns += 1;
    if (turns > pageCount + 1) {
      throw new ValidationFailure(
        "reader-render",
        "reader-navigation",
        "score reader previous-page navigation did not converge",
      );
    }
  }
  const returnedLabel = (await label.textContent()) ?? "";
  if (!/^Page(s)? 1(?:–\d+)? of \d+$/.test(returnedLabel)) {
    throw new ValidationFailure(
      "reader-render",
      "reader-navigation",
      `score reader did not return to its first page: ${returnedLabel}`,
    );
  }
  if (await selectedSession(page, target.session_id) !== target.session_id) {
    throw new ValidationFailure(
      "reader-render",
      "reader-target",
      "score reader lost its selected session",
    );
  }
  await page.getByRole("button", { name: "Workspace" }).click();
  await reader.waitFor({ state: "hidden", timeout });
  const scrubber = page.getByRole("slider", {
    name: "Recorded audio position",
  });
  await scrubber.waitFor({ state: "visible", timeout });
  const playbackSample = await scrubber.inputValue({ timeout });
  if (Number(playbackSample) !== expectedPlaybackSample) {
    throw new ValidationFailure(
      "reader-render",
      "reader-playback-state",
      `score reader changed playback sample from ${expectedPlaybackSample} to ${
        playbackSample
      }`,
    );
  }
  return {
    page_count: pageCount,
    first_label: firstLabel,
    next_label: nextLabel,
    last_label: lastLabel,
    returned_label: returnedLabel,
    playback_sample: Number(playbackSample),
  };
}

async function exerciseSession(context, target, input, browserName) {
  const started = performance.now();
  const result = {
    session_id: target.session_id,
    status: "failed",
    duration_s: 0,
    inline_svg: false,
    cursor_samples: [],
    reader: null,
    console_errors: [],
    page_errors: [],
    failed_requests: [],
    failures: [],
    screenshot: null,
  };
  const page = await context.newPage();
  page.on("console", (message) => {
    if (message.type() === "error") result.console_errors.push(message.text());
  });
  page.on("pageerror", (error) => result.page_errors.push(error.message));
  page.on("requestfailed", (request) => {
    result.failed_requests.push({
      url: request.url(),
      error: request.failure()?.errorText ?? "request failed",
    });
  });
  try {
    const url = new URL(input.base_url);
    url.searchParams.set("session", target.session_id);
    const response = await page.goto(url.href, {
      waitUntil: "domcontentloaded",
      timeout: input.timeout_ms,
    });
    if (response?.status() !== 200) {
      throw new ValidationFailure(
        "browser-runtime",
        "navigation",
        `session URL returned HTTP ${response?.status() ?? "none"}`,
      );
    }
    if (await selectedSession(page, target.session_id) !== target.session_id) {
      throw new ValidationFailure(
        "browser-runtime",
        "session-target",
        "application did not select the expected session",
      );
    }
    await page.locator(
      '[aria-label="Rendered committed MusicXML score"] svg',
    ).first().waitFor({
      state: "visible",
      timeout: input.timeout_ms,
    });
    result.inline_svg = true;
    await requireNoScoreErrors(page, "inline");

    for (const sample of target.cursor_samples) {
      const seekSample = cursorSeekSample(target, sample);
      try {
        await seek(page, seekSample, input.timeout_ms);
      } catch (error) {
        throw new ValidationFailure(
          "cursor-movement",
          "cursor",
          `cursor was not visible for attack ${sample} after seeking to ${
            seekSample
          }: ${
            error instanceof Error ? error.message : String(error)
          }`,
        );
      }
      result.cursor_samples.push({
        attack_sample: sample,
        seek_sample: seekSample,
      });
    }
    result.reader = await exerciseReader(page, target, input.timeout_ms);
    if (result.page_errors.length > 0) {
      throw new ValidationFailure(
        "browser-runtime",
        "page-exception",
        result.page_errors.join(" | "),
      );
    }
    result.status = "passed";
  } catch (error) {
    result.failures.push(failure(error));
    await mkdir(input.failure_directory, { recursive: true });
    const screenshot = path.join(
      input.failure_directory,
      `${target.session_id}-${browserName}.png`,
    );
    try {
      await page.screenshot({ path: screenshot, fullPage: true });
      result.screenshot = screenshot;
    } catch (screenshotError) {
      result.failures.push({
        category: "browser-runtime",
        stage: "failure-screenshot",
        message: screenshotError instanceof Error
          ? screenshotError.message
          : String(screenshotError),
        details: {},
      });
    }
  } finally {
    result.duration_s = (performance.now() - started) / 1000;
    await page.close();
  }
  return result;
}

async function main() {
  const input = await stdinJson();
  const report = {
    schema_version: REPORT_SCHEMA,
    status: "passed",
    client_version: null,
    browsers: [],
    failures: [],
  };
  try {
    const version = await fetch(
      `${input.base_url}/client-version.json`,
      { headers: { Accept: "application/json" } },
    );
    if (version.ok) report.client_version = await version.json();
  } catch {
    // A version document is useful evidence but not required to render scores.
  }
  for (const browserName of input.browsers) {
    const engine = engines[browserName];
    let browser;
    const browserReport = {
      name: browserName,
      version: null,
      status: "failed",
      sessions: [],
    };
    try {
      browser = await engine.launch({
        headless: input.headless,
        slowMo: input.headless ? 0 : 20,
      });
      browserReport.version = browser.version();
      const context = await browser.newContext({
        viewport: { width: 1440, height: 1000 },
      });
      await context.addCookies([{
        name: input.cookie_name,
        value: input.token,
        url: input.base_url,
        httpOnly: true,
        secure: new URL(input.base_url).protocol === "https:",
        sameSite: "Lax",
      }]);
      for (const target of input.targets) {
        browserReport.sessions.push(
          await exerciseSession(context, target, input, browserName),
        );
      }
      await context.close();
      browserReport.status = browserReport.sessions.every(
        (result) => result.status === "passed",
      ) ? "passed" : "failed";
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      browserReport.sessions.push(...input.targets.map((target) => ({
        session_id: target.session_id,
        status: "failed",
        duration_s: 0,
        failures: [{
          category: "browser-runtime",
          stage: "browser-launch",
          message: message.includes("Executable doesn't exist")
            ? `${message}\nInstall requested browsers with: npm exec --prefix app playwright -- install chromium webkit`
            : message,
          details: {},
        }],
      })));
      browserReport.status = "failed";
    } finally {
      await browser?.close();
    }
    report.browsers.push(browserReport);
  }
  report.status = report.browsers.every(
    (browser) => browser.status === "passed",
  ) ? "passed" : "failed";
  process.stdout.write(`${JSON.stringify(report)}\n`);
  process.exitCode = report.status === "passed" ? 0 : 1;
}

main().catch((error) => {
  process.stdout.write(`${JSON.stringify({
    schema_version: REPORT_SCHEMA,
    status: "failed",
    browsers: [],
    failures: [failure(error)],
  })}\n`);
  process.exitCode = 1;
});
