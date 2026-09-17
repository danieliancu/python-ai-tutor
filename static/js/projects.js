/*
 * Project workspace: saving the learner's code, checking a stage and the project coach.
 *
 * Stage availability, correctness, completion, XP and achievements are decided by Django;
 * this file only sends the code and shows the server's answer (always as text).
 */
(function (root) {
  "use strict";

  var AUTOSAVE_DELAY_MS = 4000;
  var doc = root.document;

  function boot() {
    var ui = root.CursuriUI;
    var node = doc.getElementById("project-stage-config");
    var form = doc.querySelector("[data-project-form]");
    if (!ui || !node || !form) return;
    var config = JSON.parse(node.textContent);
    var code = form.querySelector("textarea.code-field__input");
    var output = form.querySelector("[data-output]");
    var tabOutput = form.querySelector("[data-tab-output]");
    var tabErrors = form.querySelector("[data-tab-errors]");
    var runButton = form.querySelector("[data-run]");
    var saveStatus = form.querySelector("[data-save-status]");
    var nextLink = form.querySelector("[data-next-stage]");
    var syncGutter = ui.setupCodeEditor(code, form.querySelector("[data-gutter]"));
    var startedAt = Date.now();
    var savedSource = code.value;
    var timer = null;

    function showLines(lines, isError) {
      output.textContent = lines.length ? lines.join("\n") + "\n" : "";
      tabOutput.classList.toggle("is-active", !isError);
      tabErrors.classList.toggle("is-active", Boolean(isError));
    }

    function setSaveStatus(text) {
      saveStatus.textContent = text;
    }

    var save = ui.singleFlight(function () {
      var source = code.value;
      if (source === savedSource) return null;
      setSaveStatus("Saving…");
      return ui
        .request("POST", config.urls.draft, { stage: config.stage, source: source }, form)
        .then(function (result) {
          if (result.ok) {
            savedSource = source;
            setSaveStatus("Saved");
          } else {
            setSaveStatus(ui.errorMessage(result.body));
          }
          return result.ok;
        })
        .catch(function () {
          setSaveStatus("Not saved — check your connection.");
        });
    });

    function scheduleSave() {
      if (timer) root.clearTimeout(timer);
      setSaveStatus("");
      timer = root.setTimeout(save, AUTOSAVE_DELAY_MS);
    }

    var check = ui.singleFlight(function () {
      if (!code.value.trim()) {
        showLines(["Write some code first."], false);
        return null;
      }
      if (timer) root.clearTimeout(timer);
      runButton.disabled = true;
      runButton.setAttribute("aria-busy", "true");
      showLines(["Checking…"], false);
      var source = code.value;
      var body = {
        source: source,
        duration_seconds: ui.boundedDuration(Date.now() - startedAt),
      };
      return ui
        .request("POST", config.urls.submit, body, form)
        .then(function (result) {
          if (result.status === 401) {
            root.location.reload();
            return;
          }
          if (result.status !== 201) {
            // The code stays in the editor so nothing is lost.
            showLines([ui.errorMessage(result.body)], false);
            return;
          }
          var data = result.body;
          // The server saved the code before checking it.
          savedSource = source;
          setSaveStatus("Saved");
          var diagnostics = data.diagnostics || {};
          var lines = (data.feedback || []).slice();
          if (data.project_completed) lines.push("Project completed. Well done!");
          else if (data.stage_completed && data.next_stage_url) {
            lines.push("Stage complete. Continue with the next stage when you're ready.");
          }
          showLines(lines.concat(ui.rewardLines(data.rewards)), Boolean(diagnostics.error_type));
          if (data.stats) ui.updateStats(data.stats);
          if (data.stage_completed && data.next_stage_url && nextLink) {
            nextLink.setAttribute("href", data.next_stage_url);
            nextLink.hidden = false;
          }
          startedAt = Date.now();
        })
        .catch(function () {
          showLines([ui.networkError], false);
        })
        .then(function () {
          runButton.disabled = false;
          runButton.removeAttribute("aria-busy");
        });
    });

    form.addEventListener("submit", function (event) {
      event.preventDefault();
      if (!runButton.disabled) check();
    });
    form.addEventListener("keydown", function (event) {
      if (ui.isSubmitShortcut(event)) {
        event.preventDefault();
        if (!runButton.disabled) check();
      }
    });
    code.addEventListener("input", scheduleSave);

    form.querySelector("[data-save]").addEventListener("click", function () {
      if (timer) root.clearTimeout(timer);
      if (code.value === savedSource) setSaveStatus("Saved");
      save();
    });
    form.querySelector("[data-reset]").addEventListener("click", function () {
      code.value = config.resetSource || "";
      syncGutter();
      code.focus();
      scheduleSave();
    });
    form.querySelector("[data-clear]").addEventListener("click", function () {
      showLines([], false);
    });
    if (nextLink) {
      // Save before leaving so the next stage starts from the latest code.
      nextLink.addEventListener("click", function (event) {
        if (code.value === savedSource) return;
        event.preventDefault();
        var href = nextLink.getAttribute("href");
        Promise.resolve(save()).then(function () {
          root.location.assign(href);
        });
      });
    }

    ui.setupTutor(config, function (payload) {
      payload.source = code.value;
    });
  }

  if (doc.readyState === "loading") doc.addEventListener("DOMContentLoaded", boot);
  else boot();
})(window);
