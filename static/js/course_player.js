/*
 * Course player behaviour for the existing product shell.
 *
 * The browser only collects answers, sends requests and shows what the server returns.
 * Correctness, mastery, unlocking, the next exercise and tutor help levels are all decided
 * by Django. Server text is always inserted with textContent, never as HTML.
 */
(function (root) {
  "use strict";

  var MAX_DURATION_SECONDS = 86400;
  var TUTOR_COMMANDS = {
    "/hint": "hint",
    "/explain": "explain",
    "/solution": "solution",
    "/next": "next_step",
    hint: "hint",
    explain: "explain",
    solution: "solution",
  };
  var ERROR_MESSAGES = {
    tutor_turn_in_progress: "Wait for the tutor response to finish, then try again.",
    rate_limited: "You're sending messages quickly. Please wait a moment and try again.",
    tutor_rate_limited: "The tutor is busy right now. Please try again in a moment.",
    tutor_unavailable: "AI Tutor is currently unavailable.",
    assistance_unavailable:
      "Your answer could not be recorded safely right now. Please try again.",
    no_exercise_context: "Open an exercise first, then ask for help.",
    message_required: "Type a question first.",
    message_too_long: "That message is too long.",
    invalid_input: "That answer couldn't be sent. Check it and try again.",
    forbidden: "You don't have access to this right now.",
    authentication_required: "Your session has ended. Please sign in again.",
  };
  var GENERIC_ERROR = "Something went wrong. Please try again.";
  var NETWORK_ERROR = "Couldn't reach the server. Check your connection and try again.";

  // --- Pure helpers (unit-tested with node) -----------------------------------------------

  function parseTutorCommand(text) {
    var trimmed = String(text == null ? "" : text).trim();
    var key = trimmed.toLowerCase();
    if (Object.prototype.hasOwnProperty.call(TUTOR_COMMANDS, key)) {
      return { intent: TUTOR_COMMANDS[key], message: "" };
    }
    return { intent: "ask", message: trimmed };
  }

  function normaliseNumeric(text) {
    var trimmed = String(text == null ? "" : text).trim();
    if (/^[-+]?(\d+(\.\d+)?|\.\d+)$/.test(trimmed)) {
      var value = Number(trimmed);
      if (isFinite(value)) return value;
    }
    return trimmed;
  }

  function boundedDuration(milliseconds) {
    var seconds = Math.round(Number(milliseconds) / 1000);
    if (!isFinite(seconds) || seconds < 0) return 0;
    return Math.min(seconds, MAX_DURATION_SECONDS);
  }

  function isSubmitShortcut(event) {
    return event.key === "Enter" && Boolean(event.ctrlKey || event.metaKey) && !event.altKey;
  }

  function feedbackLines(attempt, statuses) {
    var lines = [statuses[attempt.status] || "Answer recorded."];
    var diagnostics = attempt.diagnostics || {};
    if (attempt.message && attempt.status !== "correct") lines.push(attempt.message);
    if (diagnostics.error_type) {
      lines.push("Error: " + diagnostics.error_type);
    } else if (diagnostics.reason && attempt.status !== "correct") {
      lines.push("Reason: " + String(diagnostics.reason).replace(/_/g, " "));
    }
    return lines;
  }

  function nextUpView(decision, text, playerUrl) {
    var action = decision.action;
    var title = "Nothing to do right now";
    if (action === "course_complete") title = "Course complete";
    else if (decision.concept) title = decision.concept.title;
    return {
      badge: text.actionLabels[action] || "Up next",
      title: title,
      description: text.reasons[decision.primary_reason] || "",
      button: text.actionButtons[action] || "Continue",
      href: decision.exercise ? playerUrl + "?exercise=" + decision.exercise.id : "",
    };
  }

  function errorMessage(body) {
    if (body && body.error && ERROR_MESSAGES[body.error]) return ERROR_MESSAGES[body.error];
    if (body && body.message) return String(body.message);
    return GENERIC_ERROR;
  }

  // Ensures an action never runs twice at once (e.g. Ctrl+Enter while a request is sent).
  function singleFlight(action) {
    var busy = false;
    return function () {
      var args = arguments;
      if (busy) return Promise.resolve(false);
      busy = true;
      return Promise.resolve()
        .then(function () {
          return action.apply(null, args);
        })
        .then(
          function () {
            busy = false;
            return true;
          },
          function (error) {
            busy = false;
            throw error;
          }
        );
    };
  }

  var helpers = {
    parseTutorCommand: parseTutorCommand,
    normaliseNumeric: normaliseNumeric,
    boundedDuration: boundedDuration,
    isSubmitShortcut: isSubmitShortcut,
    feedbackLines: feedbackLines,
    nextUpView: nextUpView,
    errorMessage: errorMessage,
    singleFlight: singleFlight,
  };
  if (typeof module !== "undefined" && module.exports) {
    module.exports = helpers;
    return;
  }

  // --- Page shell (menus and the mobile progress toggle) ----------------------------------

  var doc = root.document;

  function setupProgressToggle() {
    var toggle = doc.querySelector(".mastery__toggle");
    var progress = doc.querySelector(".side-progress");
    if (!toggle || !progress) return;
    toggle.hidden = false;
    toggle.addEventListener("click", function () {
      var open = toggle.getAttribute("aria-expanded") !== "true";
      toggle.setAttribute("aria-expanded", String(open));
      progress.classList.toggle("is-open", open);
      toggle.querySelector(".visually-hidden").textContent =
        (open ? "Hide" : "Show") + " progress details";
    });
  }

  function setupMenus() {
    var menus = Array.prototype.slice.call(doc.querySelectorAll("details[data-menu]"));
    doc.addEventListener("keydown", function (event) {
      if (event.key !== "Escape") return;
      menus.forEach(function (menu) {
        if (menu.open) {
          menu.open = false;
          menu.querySelector("summary").focus();
        }
      });
    });
    doc.addEventListener("click", function (event) {
      menus.forEach(function (menu) {
        if (menu.open && !menu.contains(event.target)) menu.open = false;
      });
    });
    menus.forEach(function (menu) {
      menu.addEventListener("click", function (event) {
        if (event.target.closest("a")) menu.open = false;
      });
    });
  }

  // --- Requests -------------------------------------------------------------------------

  function csrfToken(form) {
    var field = (form || doc).querySelector("input[name=csrfmiddlewaretoken]");
    return field ? field.value : "";
  }

  function request(method, url, body, form) {
    var options = {
      method: method,
      credentials: "same-origin",
      headers: { Accept: "application/json" },
    };
    if (body !== undefined) {
      options.headers["Content-Type"] = "application/json";
      options.headers["X-CSRFToken"] = csrfToken(form);
      options.body = JSON.stringify(body);
    }
    return root.fetch(url, options).then(function (response) {
      var type = response.headers.get("Content-Type") || "";
      var parse = type.indexOf("application/json") !== -1 ? response.json() : response.text();
      return parse.then(
        function (data) {
          return { ok: response.ok, status: response.status, body: data };
        },
        function () {
          return { ok: response.ok, status: response.status, body: null };
        }
      );
    });
  }

  // --- Exercise ---------------------------------------------------------------------------

  function setupExercise(config) {
    var form = doc.querySelector("[data-exercise-form]");
    if (!form || !config.exercise) return;
    var runButton = form.querySelector("[data-run]");
    var output = form.querySelector("[data-output]");
    var tabOutput = form.querySelector("[data-tab-output]");
    var tabErrors = form.querySelector("[data-tab-errors]");
    var code = form.querySelector("textarea.code-field__input");
    var gutter = form.querySelector("[data-gutter]");
    var startedAt = Date.now();

    function showLines(lines, isError) {
      output.textContent = lines.length ? lines.join("\n") + "\n" : "";
      if (tabOutput && tabErrors) {
        tabOutput.classList.toggle("is-active", !isError);
        tabErrors.classList.toggle("is-active", Boolean(isError));
      }
    }

    function syncGutter() {
      if (!code || !gutter) return;
      var count = code.value.split("\n").length;
      var numbers = [];
      for (var i = 1; i <= count; i += 1) numbers.push(String(i));
      gutter.textContent = numbers.join("\n");
      gutter.scrollTop = code.scrollTop;
    }

    function readAnswer() {
      var type = config.exercise.responseType;
      if (type === "multiple_choice") {
        var checked = form.querySelector("input[name=answer]:checked");
        return checked ? checked.value : null;
      }
      var field = form.querySelector("[data-answer]");
      if (!field) return null;
      if (type === "numeric") return normaliseNumeric(field.value);
      return field.value;
    }

    var submit = singleFlight(function () {
      var answer = readAnswer();
      if (answer === null || answer === "") {
        showLines(["Choose or type an answer first."], false);
        return null;
      }
      runButton.disabled = true;
      runButton.setAttribute("aria-busy", "true");
      showLines(["Checking…"], false);
      var duration = boundedDuration(Date.now() - startedAt);
      return request(
        "POST",
        config.urls.attempts,
        { answer: answer, duration_seconds: duration },
        form
      )
        .then(function (result) {
          if (result.status === 201) {
            var attempt = result.body;
            var diagnostics = attempt.diagnostics || {};
            showLines(feedbackLines(attempt, config.text.statuses), Boolean(diagnostics.error_type));
            startedAt = Date.now();
            return refreshAfterAttempt(config);
          }
          if (result.status === 401) {
            root.location.reload();
            return null;
          }
          // The learner's answer is always kept so they can try again.
          showLines([errorMessage(result.body)], false);
          return null;
        })
        .catch(function () {
          showLines([NETWORK_ERROR], false);
        })
        .then(function () {
          runButton.disabled = false;
          runButton.removeAttribute("aria-busy");
        });
    });

    form.addEventListener("submit", function (event) {
      event.preventDefault();
      if (runButton.disabled) return;
      submit();
    });
    form.addEventListener("keydown", function (event) {
      if (isSubmitShortcut(event)) {
        event.preventDefault();
        if (!runButton.disabled) submit();
      }
    });

    var reset = form.querySelector("[data-reset]");
    if (reset && code) {
      reset.addEventListener("click", function () {
        code.value = config.exercise.starterCode || "";
        syncGutter();
        code.focus();
      });
    }
    var clear = form.querySelector("[data-clear]");
    if (clear) {
      clear.addEventListener("click", function () {
        showLines([], false);
      });
    }

    if (code) {
      code.addEventListener("input", syncGutter);
      code.addEventListener("scroll", syncGutter);
      code.addEventListener("keydown", function (event) {
        // Tab indents inside the editor; Escape first lets Tab move focus on as usual.
        if (event.key === "Escape") {
          code.dataset.tabExit = "true";
          return;
        }
        if (event.key === "Tab" && !event.shiftKey && code.dataset.tabExit !== "true") {
          event.preventDefault();
          var start = code.selectionStart;
          var end = code.selectionEnd;
          code.setRangeText("    ", start, end, "end");
          syncGutter();
          return;
        }
        delete code.dataset.tabExit;
      });
      syncGutter();
    }
  }

  function refreshAfterAttempt(config) {
    var exerciseQuery = config.exercise ? "?exercise=" + config.exercise.id : "";
    var progress = request("GET", config.urls.progress + exerciseQuery).then(function (result) {
      if (!result.ok || typeof result.body !== "string") return;
      var fragment = doc.createElement("div");
      fragment.innerHTML = result.body; // server-rendered, autoescaped template
      [".ring", ".mastery__helper--mobile", "#progress-details", "#skill-map"].forEach(
        function (selector) {
          var fresh = fragment.querySelector(selector);
          var current = doc.querySelector(".side-progress " + selector);
          if (fresh && current) current.replaceWith(fresh);
        }
      );
    });
    var nextUp = request("GET", config.urls.nextAction).then(function (result) {
      if (result.ok && result.body) updateNextUp(nextUpView(result.body, config.text, config.urls.player));
    });
    return Promise.all([progress, nextUp]).catch(function () {});
  }

  function updateNextUp(view) {
    var card = doc.querySelector("[data-next-up]");
    if (!card) return;
    card.querySelector("[data-next-badge]").textContent = view.badge;
    card.querySelector("[data-next-title]").textContent = view.title;
    card.querySelector("[data-next-description]").textContent = view.description;
    var link = card.querySelector("[data-continue]");
    link.querySelector("[data-continue-label]").textContent = view.button;
    if (view.href) {
      link.setAttribute("href", view.href);
      link.removeAttribute("aria-disabled");
    } else {
      link.removeAttribute("href");
      link.setAttribute("aria-disabled", "true");
    }
  }

  // --- Tutor ------------------------------------------------------------------------------

  function setupTutor(config) {
    var form = doc.querySelector("[data-tutor-form]");
    var thread = doc.querySelector("[data-tutor-thread]");
    if (!form || !thread) return;
    var input = form.querySelector("[data-tutor-input]");
    var send = form.querySelector("[data-tutor-send]");

    function bubble(textValue, kind) {
      var node = doc.createElement("p");
      node.className = "bubble" + (kind ? " " + kind : "");
      node.textContent = textValue;
      thread.appendChild(node);
      thread.scrollTop = thread.scrollHeight;
      return node;
    }

    var ask = singleFlight(function () {
      var command = parseTutorCommand(input.value);
      if (command.intent === "ask" && !command.message) return null;
      var payload = { intent: command.intent, message: command.message };
      if (config.exercise && command.intent !== "next_step") payload.exercise_id = config.exercise.id;
      send.disabled = true;
      input.setAttribute("aria-busy", "true");
      var typed = input.value;
      var shown = bubble(typed.trim(), "bubble--learner");
      var pending = bubble("…", "bubble--pending");
      return request("POST", config.urls.tutor, payload, form)
        .then(function (result) {
          pending.remove();
          if (result.status === 201) {
            bubble(result.body.reply, "");
            if (input.value === typed) input.value = "";
            return;
          }
          if (result.status === 401) {
            root.location.reload();
            return;
          }
          shown.remove();
          bubble(errorMessage(result.body), "bubble--hint");
        })
        .catch(function () {
          pending.remove();
          shown.remove();
          bubble(NETWORK_ERROR, "bubble--hint");
        })
        .then(function () {
          send.disabled = false;
          input.removeAttribute("aria-busy");
          input.focus();
        });
    });

    form.addEventListener("submit", function (event) {
      event.preventDefault();
      if (!config.tutorAvailable || send.disabled) return;
      ask();
    });
  }

  // --- Boot -------------------------------------------------------------------------------

  function boot() {
    setupProgressToggle();
    setupMenus();
    var node = doc.getElementById("course-player-config");
    if (!node) return;
    var config = JSON.parse(node.textContent);
    setupExercise(config);
    setupTutor(config);
  }

  if (doc.readyState === "loading") doc.addEventListener("DOMContentLoaded", boot);
  else boot();
})(typeof window !== "undefined" ? window : globalThis);
