// Unit tests for the pure helpers in static/js/course_player.js (run with node).
"use strict";

const assert = require("node:assert/strict");
const path = require("node:path");

const helpers = require(path.join(process.argv[2], "static", "js", "course_player.js"));

const tests = [];
const test = (name, fn) => tests.push([name, fn]);

test("slash commands map to intents; plain text is a question", () => {
  const { parseTutorCommand } = helpers;
  assert.deepEqual(parseTutorCommand("/hint"), { intent: "hint", message: "" });
  assert.deepEqual(parseTutorCommand(" /EXPLAIN "), { intent: "explain", message: "" });
  assert.deepEqual(parseTutorCommand("/solution"), { intent: "solution", message: "" });
  assert.deepEqual(parseTutorCommand("/next"), { intent: "next_step", message: "" });
  assert.deepEqual(parseTutorCommand("hint"), { intent: "hint", message: "" });
  assert.deepEqual(parseTutorCommand("Why is range(1, 5) short?"), {
    intent: "ask",
    message: "Why is range(1, 5) short?",
  });
  // No natural-language guessing.
  assert.equal(parseTutorCommand("give me a hint please").intent, "ask");
  assert.equal(parseTutorCommand("/hint me").intent, "ask");
  assert.deepEqual(parseTutorCommand(""), { intent: "ask", message: "" });
});

test("numeric answers are sent as numbers only when clearly numeric", () => {
  const { normaliseNumeric } = helpers;
  assert.strictEqual(normaliseNumeric("42"), 42);
  assert.strictEqual(normaliseNumeric(" -3.5 "), -3.5);
  assert.strictEqual(normaliseNumeric(".25"), 0.25);
  assert.strictEqual(normaliseNumeric("+7"), 7);
  assert.strictEqual(normaliseNumeric("4321.25"), 4321.25);
  assert.strictEqual(normaliseNumeric("1e309"), "1e309");
  assert.strictEqual(normaliseNumeric("twelve"), "twelve");
  assert.strictEqual(normaliseNumeric("12cm"), "12cm");
  assert.strictEqual(normaliseNumeric(""), "");
});

test("durations are whole seconds within the accepted range", () => {
  const { boundedDuration } = helpers;
  assert.equal(boundedDuration(0), 0);
  assert.equal(boundedDuration(1499), 1);
  assert.equal(boundedDuration(-5000), 0);
  assert.equal(boundedDuration(NaN), 0);
  assert.equal(boundedDuration(10 * 86400 * 1000), 86400);
});

test("Ctrl+Enter and Cmd+Enter submit; plain Enter does not", () => {
  const { isSubmitShortcut } = helpers;
  assert.equal(isSubmitShortcut({ key: "Enter", ctrlKey: true }), true);
  assert.equal(isSubmitShortcut({ key: "Enter", metaKey: true }), true);
  assert.equal(isSubmitShortcut({ key: "Enter" }), false);
  assert.equal(isSubmitShortcut({ key: "Enter", ctrlKey: true, altKey: true }), false);
  assert.equal(isSubmitShortcut({ key: "a", ctrlKey: true }), false);
});

test("feedback shows safe text only", () => {
  const statuses = { correct: "Correct.", incorrect: "Not quite yet." };
  const { feedbackLines } = helpers;
  assert.deepEqual(
    feedbackLines(
      {
        status: "incorrect",
        message: "That code didn't pass the checks yet.",
        diagnostics: { reason: "runtime_error", error_type: "NameError" },
        submitted_answer: "print(secret)",
      },
      statuses
    ),
    ["Not quite yet.", "That code didn't pass the checks yet.", "Error: NameError"]
  );
  assert.deepEqual(
    feedbackLines({ status: "incorrect", message: "", diagnostics: { reason: "wrong_option" } }, statuses),
    ["Not quite yet.", "Reason: wrong option"]
  );
  assert.deepEqual(feedbackLines({ status: "correct", message: "Correct!" }, statuses), ["Correct."]);
});

test("next up comes straight from the server decision", () => {
  const text = {
    actionLabels: { review: "Review", course_complete: "Complete" },
    actionButtons: { review: "Review now" },
    reasons: { review_due: "Time for a quick review.", world_complete: "All done." },
  };
  const { nextUpView } = helpers;
  assert.deepEqual(
    nextUpView(
      {
        action: "review",
        primary_reason: "review_due",
        concept: { id: 3, title: "Loops over lists" },
        exercise: { id: 42 },
      },
      text,
      "/learn/worlds/1/"
    ),
    {
      badge: "Review",
      title: "Loops over lists",
      description: "Time for a quick review.",
      button: "Review now",
      href: "/learn/worlds/1/?exercise=42",
    }
  );
  const done = nextUpView(
    { action: "course_complete", primary_reason: "world_complete", concept: null, exercise: null },
    text,
    "/learn/worlds/1/"
  );
  assert.equal(done.title, "Course complete");
  assert.equal(done.href, "");
});

test("error messages are friendly and never raw", () => {
  const { errorMessage } = helpers;
  assert.match(errorMessage({ error: "tutor_turn_in_progress" }), /Wait for the tutor/);
  assert.match(errorMessage({ error: "assistance_unavailable" }), /recorded safely/);
  assert.match(errorMessage({ error: "rate_limited" }), /wait a moment/);
  assert.equal(errorMessage({ error: "tutor_unavailable" }), "AI Tutor is currently unavailable.");
  assert.equal(errorMessage({ error: "whatever", message: "Server says hi" }), "Server says hi");
  assert.equal(errorMessage(null), "Something went wrong. Please try again.");
});

test("single flight prevents double submission", async () => {
  const { singleFlight } = helpers;
  let calls = 0;
  let release;
  const run = singleFlight(() => {
    calls += 1;
    return new Promise((resolve) => {
      release = resolve;
    });
  });
  const first = run();
  const second = run(); // e.g. Ctrl+Enter pressed while the Run click is in flight
  assert.equal(await second, false);
  await Promise.resolve();
  release();
  assert.equal(await first, true);
  assert.equal(calls, 1);
  const third = run();
  await Promise.resolve();
  release();
  assert.equal(await third, true);
  assert.equal(calls, 2);
});

(async () => {
  let failed = 0;
  for (const [name, fn] of tests) {
    try {
      await fn();
      console.log(`ok - ${name}`);
    } catch (error) {
      failed += 1;
      console.log(`not ok - ${name}\n${error.stack}`);
    }
  }
  console.log(`${tests.length - failed}/${tests.length} passed`);
  process.exit(failed ? 1 : 0);
})();
