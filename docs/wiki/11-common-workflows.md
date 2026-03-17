# Chapter 11: Common Workflows

This chapter is the "what do people actually do with Halcyn all day?" chapter.

## Workflow 1: I want to see something on screen quickly

1. Launch the workbench.
2. Open Visualizer Studio.
3. Pick a simple source such as plain text.
4. Preview the scene.
5. Apply it once.

That path is good because it teaches the full loop with very little complexity.

## Workflow 2: I want to explore bar-wall scenes

1. Choose a source with multiple values, such as random values or JSON arrays.
2. Switch the scene family to a bar-wall scene.
3. Preview the output.
4. Adjust the grouping and range behavior.
5. Apply or live stream the result.

## Workflow 3: I want to prove a change is safe

1. Run the narrowest relevant test script first.
2. Fix the smallest thing needed.
3. Re-run the focused script.
4. Run `.\scripts\run-all-quality-checks.ps1`.

This keeps debugging small before it becomes large.

## Workflow 4: I want to understand a failing state

1. Open the Activity Monitor.
2. Reproduce the issue.
3. Filter the logs to the app you suspect first.
4. Check whether the problem happened:
   - before validation
   - during validation
   - after the scene was already accepted

## Workflow 5: I want to learn the codebase gently

1. Read the walkthrough chapter closest to your question.
2. Find the file or folder that owns the behavior.
3. Read the nearby tests.
4. Read the nearby comments.
5. Only then begin editing.

## Why workflows matter

Beginners often think they need to memorize the whole project.

Usually they do not.

What helps more is learning a small number of repeatable workflows. Once you
have those, the rest of the project becomes easier to place.

## Formal references for this chapter

- [Tutorial](https://gedrocht.github.io/Halcyn/tutorial.html)
- [Visualizer Studio guide](https://gedrocht.github.io/Halcyn/desktop-control-panel.html)
- [Bar-wall scene guide](https://gedrocht.github.io/Halcyn/spectrograph-suite.html)

- Walkthrough index: [Return to the walkthrough index](index.md)
- Previous chapter: [Chapter 10: How To Read the Activity Monitor](10-how-to-read-the-activity-monitor.md)
- Next chapter: [Chapter 12: Troubleshooting Without Panic](12-troubleshooting-without-panic.md)
