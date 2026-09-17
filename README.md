# cursuri.net

**cursuri.net** is a learning platform. It hosts courses, called Worlds in the code: Python Foundations today, with Django, Data Analysis, AI, Automation, AI Agents, English and more to come. Each course has its own curriculum and a personal **AI Tutor**, which is a feature of the platform rather than its name.

```
cursuri.net            the platform (settings.PRODUCT_NAME)
  └─ Course / World    Python Foundations, Django, … (World.title, World.domain)
       └─ AI Tutor     tutoring inside a course
```

This repository started as the Django foundation for that product, beginning with Python. Phase 0 set up the project structure, configuration, a custom user model, admin and a health check. Phase 1 adds the product shell, a static demo of the learning interface on the homepage. It is presentation only: the progress, skill map, lesson, editor and tutor content on the page are placeholder data.

Phase 2 adds the curriculum engine:

- a curriculum database structure: World → Skill → Concept → Lesson
- explicit Skill and Concept prerequisites, validated to stay within one World and free of cycles
- the Python Foundations seed (11 skills, 53 concepts with learning objectives, lessons and prerequisite graphs)
- Django admin for all curriculum models and a `published_curriculum()` query helper

Phase 2B adds learner accounts:

- signup, login with username or email (case-insensitive), POST-only logout and password reset
- a learner profile (preferred name, time zone) separate from the user account
- onboarding: choose a preferred name and enroll in a published learning path (World)
- enrollments: a learner can be enrolled in any number of Worlds
- an account menu on the homepage and admin for profiles and enrollments

Phase 3 adds a domain-neutral Exercise Engine. An `Exercise` belongs to a Lesson and works the same way for any subject (Python now; languages or maths later). Two separate fields describe it:

- `response_type`: how the learner answers (`code`, `multiple_choice`, `fill_gap`, `text`, `translation`, `numeric`, `math_expression`, `speaking`, `listening`)
- `learning_mode`: which cognitive level it trains (`recognise`, `complete`, `fix`, `create`)

For example: `code` + `fix` (debug a program), `translation` + `create` (translate a sentence), `multiple_choice` + `recognise` (pick the right keyword).

`content` holds what the learner sees and is validated so it never contains answers. `evaluation_spec` holds the private answer configuration for the future evaluation engine; it is never included in `exercise_presentation()` or any template. Learners only reach exercises whose whole curriculum chain is published, in Worlds where their enrollment is active or completed (`apps/exercises/access.py`).

Phase 3P adds the first real content pack: 147 Python Foundations exercises covering all 11 skills and 53 concepts. Each skill uses all four learning modes (recognise → complete → fix → create), mostly as multiple-choice, fill-the-gap and code exercises. Every exercise has a private evaluation spec: the correct option, accepted gap answers, or code tests (`stdout` or `function` strategy) with a reference solution. The definitions live in `apps/exercises/data/python_foundations/`.

Phase 4 adds a generic, deterministic Evaluation Engine (`apps/evaluation/`). `evaluate_exercise(exercise, answer)` picks an evaluator from the exercise's `response_type` and returns an in-memory `EvaluationResult` (status, score 0.0–1.0, is_correct, a safe message and internal reason codes). Nothing is stored yet.

- Evaluated automatically now: multiple choice, fill the gap and numeric (with an optional tolerance).
- Deferred: code (the Python runner comes in Phase 4P), text rubrics, translations and maths expressions (returned as `review_required`), speaking and listening (`unsupported`).
- Learner-facing output (`evaluation_result_presentation`) never includes correct options, accepted answers, expected values or tests. A misconfigured exercise raises `EvaluationConfigurationError` instead of marking the learner wrong.
- `evaluation_spec` contracts are now validated; a published exercise needs a complete one.

Phase 4P adds isolated execution for Python code exercises (`apps/python_runner/`). Learner code never runs in the Django process or directly on the host; it runs only in a throw-away Docker container:

- no network, read-only root filesystem, non-root user, all Linux capabilities dropped, `no-new-privileges`
- memory, CPU and process limits, a time limit and a cap on captured output
- only the learner's file (plus the app's own harness for function exercises) is mounted, read-only; the only writable space is a small `/tmp`
- `stdout` exercises: each test runs the program with its input and the output is compared on the host
- `function` exercises: the function is called with each test's arguments (a fresh container per test, unless the exercise asks for one shared process) and the returned JSON value is compared on the host

Expected outputs, return values and reference solutions never enter the container. If Docker is unavailable, code answers get a safe "can't be checked right now" error and are never marked wrong. There is no local fallback. The runner is stateless and nothing is saved yet.

Phase 5 adds persistent learner history (`apps/attempts/`):

- `ExerciseAttempt`: one submission, linked to the learner's `Enrollment` and the `Exercise`, numbered 1, 2, 3… per learner and exercise. It stores the learner's own answer, the evaluation outcome (`correct`, `incorrect`, `invalid`, `review_required`, `unsupported` or `unavailable`), score, a safe message and reason codes, plus hint level, explanation/solution use and time taken.
- `AttemptMistake`: safe mistake codes extracted from the result (e.g. `wrong_option`, `output_mismatch`, `runtime_error` with the exception class).
- Answers are evaluated with the existing engine. If evaluation infrastructure fails, the attempt is stored as `unavailable`, never as incorrect.
- Correct options, accepted answers, expected values, tests and reference solutions are never stored with attempts or returned.

Authenticated JSON endpoints (session login and CSRF token required):

- `POST /app/exercises/<id>/attempts/` with `{"answer": …, "hint_level": 0, "used_explanation": false, "used_solution": false, "duration_seconds": 94}` (all but `answer` optional) → `201` with the attempt
- `GET /app/exercises/<id>/attempts/` → your latest 50 attempts for that exercise, newest first
- `GET /app/attempts/<id>/` → one of your attempts, including your submitted answer

Only learners with an active or completed enrollment can use them, and only for exercises that are currently published.

Phase 6 adds deterministic learner intelligence (`apps/learner_intelligence/`). After every stored attempt, the learner's state for that concept is recalculated from their attempt history:

- **Mastery** (0–100, band `not_started` / `weak` / `learning` / `practising` / `mastered`): recent judged attempts, weighted by learning mode (recognise < complete < fix < create), recency and how much help was used. One answer can't give full mastery. Recognition alone is capped at 65, completion at 80 and fixing at 90, and `mastered` needs a correct fix or create answer.
- **Mode performance**: a separate score for recognise, complete, fix and create.
- **Independence**: success without hints, explanations or solutions.
- **Fluency**: correct, independent and within the exercise's target time. Empty when there is no timing data.
- **Retention**: correct answers at least 24 hours after the previous attempt. Quick repetition doesn't count, and the score is empty until spaced evidence exists.
- **Trend**: `rising`, `stable` or `falling` (latest 3 attempts against the 3 before), once there are 6 judged attempts.
- **Review due**: `review_due_at` comes from mastery and retention (0–60 days after the last judged attempt). Whether a concept is due is worked out when read.

Only `correct` and `incorrect` attempts count; unsupported, unavailable, invalid and review-required attempts never lower a score. Attempts remain the source of truth: `ConceptState` and `ConceptModeState` are derived, versioned (`algorithm_version`) and rebuildable with `python manage.py rebuild_learner_intelligence` (optionally `--enrollment-id` or `--world-slug`). If a refresh fails, the attempt is still saved and the error is logged. No AI makes these decisions. There is no next-best-action yet.

`GET /app/worlds/<id>/learning-state/` (session login, active or completed enrollment) returns your read-only Student State for a World: summary counts, per-skill summaries and per-concept signals, without answers or evaluation data. The learning state can't be written through the API; the admin shows it read-only.

Phase 6B adds deterministic misconception detection (`apps/misconceptions/`). An `AttemptMistake` records what went wrong in one submission (for example `output_mismatch`). A `MisconceptionState` is a learning pattern inferred from repeated evidence (for example `range-exclusive-stop`), tracked per enrollment and concept:

- **Evidence.** After every attempt, detectors turn the attempt into `MisconceptionEvidence`:
  - A failed exercise gives weak candidate evidence for each misconception tag in its private `evaluation_spec["misconceptions"]`.
  - Deterministic Python rules give strong evidence when the mistake is unambiguous. They cover: a range stop one too low, a reversed comparison, `>` versus `>=`, a missing or wrongly signed range step, a `while` loop that timed out, `IndentationError`/`TabError`, and a swapped `break`/`continue`. The rules only read the code (Python `ast`); learner code never runs inside Django.
  - A correct answer is counter-evidence. Its weight drops when hints, explanations or the solution were used.
- **Confidence** is a deterministic 0–100 evidence score, not a probability. Recent evidence counts more, and one submission counts only once per misconception.
- **Statuses:**
  - `watch`: some evidence, not yet persistent. One wrong answer never goes further than this.
  - `active`: confidence of at least 60 plus recurring evidence (two different exercises, three failed attempts, or two strong detector hits).
  - `resolved`: it was active, confidence has dropped below 30, and at least two meaningful correct answers came after the last failure. A resolved misconception becomes active again if the evidence comes back.
- **Rebuilding.** Raw mistake codes are never misconceptions on their own. Evidence and state are derived, versioned and rebuildable with `python manage.py rebuild_misconceptions` (optionally `--enrollment-id` or `--world-slug`). A failed refresh never removes the attempt or the learner-intelligence state.
- **Student State.** The learning-state endpoint lists each concept's active and watched misconceptions (code, title, status, confidence) and counts them in its summary. Evidence, answers and exercise specs are never exposed.

No AI decides any of this.

Phase 7 adds a deterministic Next Best Action (`apps/next_action/`). `GET /app/worlds/<id>/next-action/` (session login, own active or completed enrollment, read-only) answers "what should I do next?" with an action (`learn`, `practice`, `review`, `remediate`, `course_complete` or `no_available_action`), reason codes, the concept, lesson and exercise (safe presentation only), a target learning mode and any related misconceptions. Priorities, highest first:

1. **Remediate** a concept with an active misconception, preferring exercises tagged with it.
2. **Review** a concept whose review date has passed.
3. **Strengthen** a started concept whose mastery is below 65.
4. **Learn** the next new concept, in authored order, once its prerequisites are ready.
5. **Deepen** a concept that is learned but not mastered, has an untried stronger learning mode, has a weak mode, is falling, or has watched misconceptions.

How the rules work:

- **Prerequisites.** A new concept unlocks when every concept prerequisite, and every published concept of each prerequisite skill, has mastery of at least 65. New content never waits for mastery 85. Prerequisites only gate new concepts; started concepts always stay available.
- **Urgency and ties.** Within a tier, urgency (overdue days, retention, mastery gap, a falling trend, watched misconceptions, a small bonus for continuing the current concept) and then curriculum order break ties. Urgency never outranks a higher tier.
- **Exercise choice.** The target mode is the first mode without a correct answer (recognise → complete → fix → create), otherwise the weakest one, and only among modes that have published exercises. The picker then prefers a matching lesson kind, then exercises not in the last three attempts, then unattempted ones.
- **Finishing.** `course_complete` needs every published concept mastered, with nothing to remediate and no review due. A learner who is blocked by prerequisites or by missing exercises gets `no_available_action` instead.

Decisions are computed on each request and never stored. No AI is involved, and there is no learner interface yet. `python manage.py explain_next_action <enrollment_id> [--now ISO]` prints a decision, including the internal ranking, for debugging.

Phase 8 adds a generic AI tutor (`apps/ai_tutor/`). **Django stays the source of truth**: correctness, scores, mastery, misconceptions, review dates and the next best action come only from the deterministic engines above. The model only writes the teaching reply.

- **Provider.** Replies come from the OpenAI Responses API through the official SDK, with `store=false`, a strict JSON output schema (`reply`, `response_kind`, `should_retry`) and no tools. The model is set by `OPENAI_MODEL` (default `gpt-5.6-luna`). Everything provider-specific sits behind a provider interface.
- **Context.** Each turn gets a compact, server-built context: the World, the current concept, lesson and exercise (safe presentation), the latest evaluated attempt, concept state, active and watched misconceptions, the next best action, a World summary and the last few completed tutor turns. Exercise answer keys, specs, tests and reference solutions are never included. The learner's own latest answer (up to 8 KB) is sent separately and marked as untrusted data. Learner text is never placed in the trusted instructions.
- **Help ladder.** Intents are `ask`, `hint`, `explain`, `solution` and `next_step`. Django decides the reply level: hint → strong hint → explanation → solution. Asking for the solution straight away starts with a hint, and a reply at any other level is rejected.
- **Assistance tracking.** AI help given on an exercise is stored and merged into the learner's next attempt: hint level uses the higher value, explanation and solution use either flag. The client can't hide it, so the Phase 6 assistance discount applies. Each new attempt resets the record. Submitting an answer never calls the AI.
- **Conversations and usage.** Turns are stored in our database (`TutorTurn`): messages, reply level, status, model, prompt version, token usage and latency. Prompts and provider payloads are not stored.
- **Failures and limits.** Provider failures are recorded as failed turns with a safe error code and never change learning state. Each enrollment is limited to 20 tutor requests per minute (configurable).

Endpoints (session login, own active or completed enrollment; POST needs the CSRF token):

- `POST /app/worlds/<id>/tutor/turns/` with `{"intent": "hint", "exercise_id": 123}` or `{"message": "Why is this wrong?", "exercise_id": 123}` → `201` with the reply and the current assistance record. Responses: `503 tutor_unavailable` when the tutor is disabled or the provider fails, `429 rate_limited`, `400 no_exercise_context` when help has no exercise to refer to.
- `GET /app/worlds/<id>/tutor/turns/?limit=20` → your recent completed turns, oldest first (at most 50).

Enable it with, for example:

```bash
AI_TUTOR_ENABLED=true
OPENAI_API_KEY=your-key-here
OPENAI_MODEL=gpt-5.6-luna
```

Tests never call the provider.

Phase 8P hardens the tutor and adds Python-specific teaching.

**Integrity of AI help**

- **One reply at a time per exercise.** A learner can have only one tutor request in progress for each exercise; the database enforces this. A second request gets `409 tutor_turn_in_progress` and never reaches the provider, so two parallel requests can't both move up the help ladder from the same step. Requests left unfinished (for example after a crash) are closed after `max(120 s, 4 × OPENAI_TIMEOUT_SECONDS)`.
- **The record of help comes from history.** AI help is rebuilt from completed tutor turns since the learner's latest attempt; turns keep a `completed_at` time. The per-exercise record (`TutorExerciseState`) is just a stored copy, repaired whenever it is read. `python manage.py rebuild_tutor_assistance [--enrollment-id N]` rebuilds all of these copies.
- **Fail closed.** When an answer is submitted, the server's record of AI help is authoritative: the client can report more help, never less. If that record can't be determined, the answer is refused with `503 assistance_unavailable` instead of trusting the client. While a tutor reply for the same exercise is still being generated, submission returns `409 tutor_turn_in_progress`. With the tutor switched off, submissions work as usual.

**Python teaching**

- **Domains.** Each World now has a `domain` (`general` by default; Python Foundations is `python`), and the tutor picks its domain adapter from that field.
- **What the Python tutor sees.** Beyond the generic context, it gets static facts about the learner's latest code (Python `ast` parsing only; the tutor never runs code, and the runner remains the only place code is executed). It also gets the deterministic outcome category (syntax error, runtime error, wrong output, wrong result, timeout, output limit, and so on), the mistake codes, and active and watched misconceptions as its teaching focus. Remediation targets the active misconception.
- **How it teaches.** Its instructions ask it to teach like a programming teacher: one narrow step at a time, adapted to the learning mode (recognise, complete, fix, create) and the help level.
- **Answer keys only at the solution stage.** The authored answer reaches the model only when the solution is granted, and only the minimum needed: the reference solution, the accepted fill-in answers, the correct option, or the expected number. Hidden tests, expected outputs and the evaluation spec never do, and answers are never stored.
- **Leak guard.** Before the solution stage, a reply that reproduces the reference solution is rejected and never stored.
- **Not yet built:** the Course Player (learner interface).

Phase 8B turns the existing product shell into the real **Course Player** (`apps/course_player/`). The design is deliberately unchanged: same layout, colours, typography and responsive behaviour. Only real data and working controls were added.

Learner flow: sign in → `/` sends you to your course (`/learn/worlds/<id>/`, your first active enrollment) → the exercise chosen by Next Best Action is shown → answer it → **Run Code** / **Check answer** (or <kbd>Ctrl</kbd>/<kbd>Cmd</kbd> + <kbd>Enter</kbd>) → deterministic feedback in the Output panel → mastery, skill map and **Next Up** refresh → ask the AI Tutor → **Continue** opens the next recommended exercise.

**The page**

- **Exercise types.** Code (an editable editor with Reset), multiple choice, fill the gap, numeric and text answers all appear inside the existing exercise card.
- **Recording answers.** Every Run/Check records an attempt through `POST /app/exercises/<id>/attempts/` (with the time spent). The Output panel shows only safe feedback: the result, the evaluator's message and the error type. Hidden tests, expected output and solutions never reach the page.
- **Data shown.** Signed-in learners see only real data: mastery (the average over published concepts), the current skill, and a skill map derived from learner state. XP, streak and level show neutral placeholders until gamification exists.
- **After an answer.** The page refreshes the left panel from `GET /learn/worlds/<id>/progress/` (a server-rendered fragment, so lock and progress states stay server-side) and Next Up from `GET /app/worlds/<id>/next-action/`.

**AI Tutor panel**

- Shows your recent conversation.
- Plain text is a question.
- `/hint`, `/explain`, `/solution` and `/next` ask for help or the next step. The server decides the help level.
- If the tutor is unavailable, exercises keep working.
- Practice, Projects, Community, search and the feedback thumbs stay inactive.
- Signed-out visitors still see the static demo.

Phase 9 adds **gamification** (`apps/gamification/`) and the **cursuri.net** brand. Gamification rewards learning but never decides it: evaluation still decides correctness, Learner Intelligence mastery, the Misconception Engine misconceptions and Next Best Action what comes next. XP never raises mastery, and levels, streaks and achievements never unlock content. Everything is generic (any World, any domain) and computed on the server.

**Branding.** The top-left brand, page titles (`<lesson> · <course> · cursuri.net`), footer, account pages and emails use `settings.PRODUCT_NAME` through the `config.context_processors.product` context processor. The current course comes from the World: the breadcrumb and the mastery title (for example "Python Foundations Mastery"). Nothing generic hardcodes Python. The signed-out demo still shows Python Foundations content under the cursuri.net brand.

**XP.** XP is platform-wide per learner: the header shows one total across all courses. Each award is an `XPEvent` that keeps its World and enrollment for later per-course analytics. The event log is the source of truth, and `GamificationProfile.total_xp` is a recomputable summary.

| Award | XP | When |
|---|---|---|
| Exercise completed | 20 | The first correct attempt at an exercise |
| First-try bonus | 5 | The learner's very first attempt at that exercise was correct |
| Independence bonus | 5 | That first correct attempt used no hints, explanation or solution (server-recorded `hint_level`, `used_explanation`, `used_solution`) |
| Skill mastered | 50 | Every published concept in a Skill first reaches the mastered band |
| Boss completed | 100 (`bonus_xp`) | A Boss Challenge's exercise is first answered correctly |

- **Once per learner.** Each award has a unique `(learner, source_key)` database constraint, so retries, repeated correct answers, concurrent submissions and rebuilds never award XP twice.
- **Never taken away.** XP is never negative and is never removed, even if retention later drops.
- **Help costs nothing but the bonus.** Using AI help only means no independence bonus.
- **What earns nothing.** Page views, tutor questions, wrong answers and answers that couldn't be judged (`invalid`, `unsupported`, `unavailable`) never earn XP.

**Levels.** Levels are derived from XP and never stored. Reaching level N takes `100 × N × (N − 1) / 2` XP: level 2 at 100, level 3 at 300, level 4 at 600, level 5 at 1000. All level maths lives in `apps/gamification/levels.py`. The header gauge shows progress from the current level's threshold to the next.

**Streaks.** A streak counts consecutive calendar days, in Django's configured time zone (`TIME_ZONE`), with at least one judged attempt (`correct`, `incorrect` or `review_required`) in any course.
- Many attempts on one day count as one day.
- A streak stays alive through the day after the last activity and breaks after that.
- The longest streak is kept.

**Achievements.** Achievements are non-repeatable, awarded by the server and seeded by a migration. They are listed on the profile page, and a new one is also mentioned in the exercise output right after the attempt that earned it.

| Achievement | Rarity | Earned by |
|---|---|---|
| First Step | common | First correctly completed exercise |
| Independent Thinker | uncommon | A correct completion without hints, explanation or solution |
| On a Roll | common | A 3-day streak |
| Consistent Learner | rare | A 7-day streak |
| Skill Mastered | rare | First fully mastered Skill |
| Boss Cleared | epic | First Boss Challenge |
| Ten Down | uncommon | 10 different exercises completed correctly |

**Boss Challenges.** A `BossChallenge` marks an existing Exercise as a checkpoint. The prompt, evaluation and runner stay on the Exercise, and the checkpoint is not a project system: Phase 10 Projects are not implemented yet.
- **Availability.** A boss follows the normal curriculum, prerequisites and Next Best Action. Being a boss never unlocks anything.
- **Python Foundations bosses.** `seed_python_exercises` marks four existing CREATE code exercises:
  - `ticket-price` (decisions)
  - `years-to-double` (loops)
  - `bank-account` (OOP)
  - `full-class-report` (the capstone)
- **Completion.** A boss is completed once per enrollment (`BossCompletion`).
- **Display.** When the current exercise, or the one Next Best Action recommends, is a boss, the Course Player labels it "Boss Challenge".

**In the Course Player**
- The header shows the real XP, level (with gauge) and streak.
- After an attempt, the page reads `GET /app/gamification/summary/?attempt=<id>`. The response carries the updated stats plus what that attempt earned (for example "+30 XP" or "Achievement unlocked: First Step"). The browser only displays these values and never calculates them.
- Anonymous visitors keep the demo numbers.

**Recovery.** Gamification runs after learner intelligence and misconceptions in the post-attempt steps. A failure is logged and never undoes the attempt. `python manage.py rebuild_gamification` (optionally `--learner-id` or `--enrollment-id`) recomputes XP, levels, streaks, boss completions and achievements from stored attempts. Running it again changes nothing. Attempts made before Phase 9 are fully covered, including the first-try and independence bonuses. Skill-mastery milestones are reconciled from the *current* learner-intelligence state, so a skill mastered in the past and since decayed is not rewarded retroactively. The admin lists every Phase 9 model; there are no leaderboards and no virtual currency.

**Available:** curriculum data, learner accounts, profiles, World enrollment, the Python Foundations exercises (editable in the admin), answer evaluation, isolated Python execution, saved attempt history, deterministic learner state, misconception detection, next-best-action decisions, the AI tutor with Python-specific teaching, the browser Course Player and gamification (XP, levels, streaks, achievements, Boss Challenges).
**Not yet implemented:** Phase 10 Projects, Practice, Community, search, leaderboards, voice, streaming replies and billing.

## Stack

- Python 3.11+
- Django 5.2 (LTS)
- PostgreSQL in production, with SQLite as the zero-setup local default
- Django templates with HTMX 2.0.10, stored locally in `static/vendor/`
- Configuration through environment variables (`.env` is loaded with `python-dotenv`)
- ruff for linting and formatting

## Project layout

```
config/          Django project: settings, URLs, WSGI/ASGI, env helpers, root views
apps/accounts/   Custom user model (AUTH_USER_MODEL = "accounts.User"), signup/login/password reset
apps/curriculum/ Curriculum models, admin, selectors, seed data and seed_curriculum command
apps/learners/   Learner profiles, World enrollment, onboarding and the profile page
apps/exercises/  Exercise model, validation, safe presentation, selectors, access rules and the
                 Python Foundations exercise pack (data/ + seed_python_exercises command)
apps/evaluation/ Evaluation engine: result type, evaluator registry and evaluators
apps/python_runner/ Docker-isolated Python execution and the Python code evaluator
apps/attempts/   Learner attempt history, mistake codes and the attempt JSON endpoints
apps/learner_intelligence/ Derived learner state (mastery, retention, review), Student State
                 endpoint and the rebuild_learner_intelligence command
apps/misconceptions/ Misconception catalog, detectors (generic + Python), derived evidence/state
                 and the rebuild_misconceptions command
apps/next_action/ Deterministic next-best-action engine and its read-only JSON endpoint
apps/course_player/ The learner Course Player: real data and interactions for the product shell
apps/gamification/ XP events, levels, streaks, achievements, Boss Challenges, the stats summary
                 endpoint and the rebuild_gamification command
apps/ai_tutor/    AI tutor: context builder, help ladder, providers (OpenAI, fake), domain
                 adapters (domains/python), assistance reconstruction,
                 conversation history and the tutor JSON endpoints
templates/       Project-level templates
static/          Project-level static files (css/, js/course_player.js, vendor/htmx.min.js)
```

## Local setup

### Windows (PowerShell)

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
Copy-Item .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

### macOS / Linux

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
cp .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

### Running the full learning experience

1. Copy the example settings: `cp .env.example .env` (Windows: `copy .env.example .env`).
2. Edit `.env` for the AI tutor:

   ```bash
   AI_TUTOR_ENABLED=true
   OPENAI_API_KEY=YOUR_OPENAI_KEY
   ```

   `.env` is git-ignored; never commit a real key. With the key left empty, the tutor simply shows as unavailable.
3. To run code exercises for real, install Docker, pull the runner image and set `PYTHON_RUNNER_BACKEND=docker` in `.env`:

   ```bash
   docker pull python:3.11-slim
   ```

   Without Docker, code answers are reported as "can't be checked automatically yet", never as wrong.
4. Prepare the data and start the server:

   ```bash
   python manage.py migrate
   python manage.py seed_curriculum
   python manage.py seed_python_exercises
   python manage.py runserver
   ```

5. Sign up, choose Python Foundations during onboarding, and you land in the Course Player.

### Curriculum and exercise data

Load or refresh the Python Foundations curriculum and its exercises after migrating (in this order):

```bash
python manage.py migrate
python manage.py seed_curriculum
python manage.py seed_python_exercises
```

Both seeds are idempotent. Records are matched by slug within their parent, so running them again updates the seeded records (repairing manual edits) without duplicating them, and they never delete records they don't define. `seed_python_exercises` stops with an error if the curriculum hasn't been seeded yet.

Once the server is running, these URLs are available:

- http://127.0.0.1:8000/: homepage, the static learning-interface demo (product shell)
- http://127.0.0.1:8000/health/: returns `{"status": "ok"}`
- http://127.0.0.1:8000/admin/: Django admin
- http://127.0.0.1:8000/accounts/signup/: create an account
- http://127.0.0.1:8000/accounts/login/: sign in with email or username
- http://127.0.0.1:8000/accounts/password-reset/: request a password reset link
- http://127.0.0.1:8000/onboarding/: choose a name and a learning path (signed-in users)
- http://127.0.0.1:8000/profile/: your profile and enrollments (signed-in users)

Logging out is a POST to `/accounts/logout/` (the account menu and profile page provide the button).

In development, password reset emails are printed to the console where `runserver` is running.

## Configuration

Every setting is read from environment variables. See [.env.example](.env.example) for the full list. Real environment variables take precedence over `.env`. Never commit `.env`.

| Variable | Default | Notes |
|---|---|---|
| `DJANGO_SECRET_KEY` | (none) | Required when `DJANGO_DEBUG=false`. When DEBUG is on and this is empty, an insecure development-only key is used. |
| `DJANGO_DEBUG` | `false` | Boolean. |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | Comma-separated. |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | empty | Comma-separated. Each entry **must include the scheme**, e.g. `https://example.com`. |
| `DJANGO_TIME_ZONE` | `UTC` | |
| `DJANGO_LOG_LEVEL` | `INFO` | |
| `DATABASE_URL` | SQLite `db.sqlite3` | For example `postgres://user:pass@host:5432/dbname`. |
| `DATABASE_CONN_MAX_AGE` | `60` | Seconds. `0` closes the connection after each request. |
| `DJANGO_SECURE_SSL_REDIRECT` | `true` | Only applies when DEBUG is off. |
| `DJANGO_SECURE_HSTS_SECONDS` | `0` | Only applies when DEBUG is off. Increase it gradually once HTTPS is confirmed. |
| `DJANGO_SECURE_PROXY_SSL_HEADER` | `false` | See the warning below. |
| `DJANGO_EMAIL_BACKEND` | console backend | Where password reset emails go. Use `django.core.mail.backends.smtp.EmailBackend` (plus Django's `EMAIL_*` settings) for real delivery. |
| `DJANGO_DEFAULT_FROM_EMAIL` | `cursuri.net <no-reply@localhost>` | Sender address for account emails. |
| `PYTHON_RUNNER_BACKEND` | `disabled` | `docker` enables code execution. Anything else keeps code exercises unchecked. |
| `PYTHON_RUNNER_IMAGE` | `python:3.11-slim` | Runner image. It is never pulled automatically. |
| `PYTHON_RUNNER_TIMEOUT_SECONDS` | `3` | Time limit per run (0.1–60). |
| `PYTHON_RUNNER_MEMORY_MB` | `128` | Memory limit, swap included (32–4096). |
| `PYTHON_RUNNER_CPUS` | `0.5` | CPU limit (0.05–8). |
| `PYTHON_RUNNER_PIDS_LIMIT` | `64` | Maximum processes/threads in the container. |
| `PYTHON_RUNNER_MAX_OUTPUT_BYTES` | `65536` | Output cap; the run is stopped when exceeded. |
| `PYTHON_RUNNER_MAX_SOURCE_BYTES` | `65536` | Largest accepted submission. |
| `PYTHON_RUNNER_DOCKER_BINARY` | `docker` | Path to the Docker CLI. |
| `AI_TUTOR_ENABLED` | `false` | Boolean. The tutor also needs an API key. |
| `OPENAI_API_KEY` | empty | Never commit a real key. |
| `OPENAI_MODEL` | `gpt-5.6-luna` | Model used for tutor replies. |
| `OPENAI_TIMEOUT_SECONDS` | `20` | Provider timeout (1–300). |
| `AI_TUTOR_HISTORY_TURNS` | `8` | Completed turns sent as conversation history. |
| `AI_TUTOR_MAX_USER_CHARS` | `4000` | Longest accepted learner message. |
| `AI_TUTOR_MAX_OUTPUT_TOKENS` | `800` | Reply token cap. |
| `AI_TUTOR_RATE_LIMIT_PER_MINUTE` | `20` | Tutor requests per enrollment per minute. |

Booleans accept `true/false`, `1/0`, `yes/no` and `on/off`, in any case. Any other value stops startup with an error. In list values, surrounding whitespace and empty entries are ignored.

> **`DJANGO_SECURE_PROXY_SSL_HEADER`**: enable this **only** when Django runs behind a trusted reverse proxy that always sets `X-Forwarded-Proto` and removes any value sent by the client. If you enable it anywhere else, clients can make plain HTTP requests look like HTTPS.

To generate a secret key:

```bash
python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"
```

### Using PostgreSQL locally

1. Create a database and a user in PostgreSQL.
2. Set the connection URL in `.env`:
   ```
   DATABASE_URL=postgres://app_user:app_password@localhost:5432/app_db
   ```
3. Run `python manage.py migrate`.

The `psycopg[binary]` driver is already listed in `requirements.txt`.

### Python code runner

Code exercises are checked only when Docker is available and the runner is enabled:

```bash
docker pull python:3.11-slim
# in .env
PYTHON_RUNNER_BACKEND=docker
```

Invalid runner settings stop startup with a clear error; a stopped Docker daemon doesn't (code answers just can't be checked until it is back). For production, pin the image to an immutable digest, e.g. `PYTHON_RUNNER_IMAGE=python:3.11-slim@sha256:<digest from docker pull>`.

Docker containers on the application host are a reasonable boundary for this stage, but they are not perfect isolation. A public, multi-tenant deployment should move execution to dedicated runner hosts and consider stronger sandboxing (for example microVM-based runtimes or strict orchestration policies).

## Development commands

```bash
python manage.py check                  # Django system checks
python manage.py makemigrations --check --dry-run   # fails if model changes lack migrations
python manage.py test                   # run the test suite (never needs Docker)
python manage.py rebuild_learner_intelligence   # recalculate learner state from attempts
python manage.py rebuild_misconceptions          # recalculate misconceptions from attempts
python manage.py explain_next_action <enrollment_id>   # show one learner's next action
python manage.py rebuild_tutor_assistance        # rebuild AI help records from history
python manage.py rebuild_gamification            # rebuild XP, streaks, bosses and achievements
ruff check .                            # lint
ruff format .                           # format (use --check in CI)
```

The Docker runner has an opt-in integration suite (real containers; includes checking every seeded reference solution, which takes several minutes):

```powershell
docker pull python:3.11-slim
$env:PYTHON_RUNNER_INTEGRATION = "1"
python manage.py test apps.python_runner.tests
```

## Dependencies

- `requirements.txt` lists the direct runtime dependencies with compatible version ranges.
- `requirements-dev.txt` adds the development tools.
- Neither file is a frozen lock file.
