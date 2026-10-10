# Queue Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist several Codex drafts locally and automatically deliver them in order after a user-supplied usage-reset time.

**Architecture:** A small JSON-backed queue repository owns draft serialization and settings. A testable runner owns due-time, pause, confirmation and delivery transitions; `app.py` presents it in a compact Tkinter UI while the existing Windows adapter keeps sending behavior unchanged.

**Tech Stack:** Python 3.14, Tkinter, dataclasses, JSON, unittest, Windows clipboard APIs.

**Spec:** `docs/superpowers/specs/2026-10-10-queue-recovery.md`

## Global Constraints

- Use Python standard library only; run on Windows.
- Store data only below `%LOCALAPPDATA%\\CodexTimedSender\\queue.json`; no account data or network access.
- Do not persist target-window handles; require binding after every application launch.
- Preserve text/path/image delivery behavior and the existing send-key choice.

## Review Focus

- Restart after adding drafts: queued content and settings must load exactly once, without corrupting a partially-written JSON file.
- Recovery time in the past: the first pending item is eligible immediately once the queue starts.
- Invalid or closed target window: no clipboard paste/send occurs and the failed item is retained.
- Delivery failure after an image paste: the queue pauses and does not attempt the next message.
- “First item confirmation” enabled: a successful first item never triggers the second until the user resumes.

---

### Task 1: Persistent queue model and repository

**Files:**
- Create: `timed_sender/queue.py`
- Modify: `timed_sender/models.py`
- Test: `tests/test_queue.py`

**Interfaces:**
- Produces `QueueItem`, `QueueSettings`, `QueueStore(path: Path)`, `load()`, `save(items, settings)`, `add()`, `update()`, `move()` and `delete()` for the runner and UI.

- [ ] **Step 1: Write failing repository tests** for adding two drafts, changing their order, persisting reset settings, and retaining failed status after a reload.
- [ ] **Step 2: Run `python -m unittest tests.test_queue -v`** and confirm it fails because `timed_sender.queue` does not exist.
- [ ] **Step 3: Implement the dataclasses and JSON repository** with atomic replacement of the completed JSON file and a default local-app-data location.
- [ ] **Step 4: Run `python -m unittest tests.test_queue -v`** and confirm all queue tests pass.
- [ ] **Step 5: Commit** with `feat: add persistent delivery queue`.

### Task 2: Queue runner and delivery transitions

**Files:**
- Create: `timed_sender/queue_runner.py`
- Test: `tests/test_queue_runner.py`

**Interfaces:**
- Consumes: `QueueItem`, `QueueSettings`, `QueueStore`, `DeliveryService` and `TargetWindow` from Task 1/current code.
- Produces `QueueRunner.tick(now, target) -> QueueRunResult` and `QueueRunner.resume()`.

- [ ] **Step 1: Write failing runner tests** for waiting before reset, successful in-order delivery at reset, interval enforcement, failure-pauses-and-retains, and confirmation after first success.
- [ ] **Step 2: Run `python -m unittest tests.test_queue_runner -v`** and confirm it fails because `timed_sender.queue_runner` does not exist.
- [ ] **Step 3: Implement the minimal state transitions**, saving after every status or settings change and delegating actual send work to `DeliveryService`.
- [ ] **Step 4: Run `python -m unittest tests.test_queue_runner -v`** and confirm all runner tests pass.
- [ ] **Step 5: Commit** with `feat: run queued deliveries after reset`.

### Task 3: Compact Tkinter queue interface

**Files:**
- Modify: `app.py`
- Modify: `tests/test_app.py`
- Modify: `README.md`

**Interfaces:**
- Consumes Task 1 repository and Task 2 runner; binds transient `TargetWindow` before starting.
- Produces controls to create/edit/reorder/delete queued drafts, configure reset time/interval/confirmation, and start/pause/resume processing.

- [ ] **Step 1: Write failing `build_queue_item`/configuration validation tests** for a missing target, invalid reset timestamp, and a valid queued item.
- [ ] **Step 2: Run `python -m unittest tests.test_app -v`** and confirm the new tests fail for missing queue-builder behavior.
- [ ] **Step 3: Replace the single-plan controls with queue controls** while retaining file-path/image selection and call `QueueRunner.tick()` from Tkinter's timer.
- [ ] **Step 4: Update README** with setup, reset-time workflow, queue status meanings, and the explicit limitation that the program does not query account allowance.
- [ ] **Step 5: Run `python -m unittest discover -s tests -p "test_*.py"` and `python -m compileall -q app.py timed_sender`**, confirming the full suite and compilation pass.
- [ ] **Step 6: Commit** with `feat: add queue recovery interface`.
