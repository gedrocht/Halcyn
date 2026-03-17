# Chapter 10: How To Read the Activity Monitor

The Activity Monitor exists so you do not have to guess what the running tools
are doing.

It is the place where Halcyn becomes less mysterious.

## What it is actually showing

The Activity Monitor reads a shared JSON-lines journal.

That means each line is one structured event written by a participating app.

In practice, that lets you see:

- when the renderer starts
- when a scene is validated
- when a scene is applied
- when a live stream begins or stops
- when a helper app reports a warning or failure

## Why this matters so much for beginners

Without a shared log, a complex project feels like many silent boxes.

With a shared log, the project starts to feel like a conversation:

- Visualizer Studio says what it sent
- the API says what it accepted or rejected
- the renderer says what it is doing with that scene

## How to read it without drowning in details

Read each event with three questions:

1. Which app said this?
2. Is it information, a warning, or an error?
3. What happened immediately before and after it?

If you do only that, the log becomes much more useful.

## Sort and filter strategy

If many things are happening at once:

- filter by one app first
- then sort by newest
- then look for the first warning or error near the time something felt wrong

That gives you a story instead of a wall of text.

## Try this now

1. Open the Activity Monitor.
2. Apply a scene once.
3. Start live streaming.
4. Stop live streaming.
5. Watch how the event sequence changes.

This teaches you the rhythm of the system very quickly.

## Formal references for this chapter

- [Testing guide](https://gedrocht.github.io/Halcyn/testing.html)
- [Control Center guide](https://gedrocht.github.io/Halcyn/control-center.html)

## Helpful external references

- [Python logging cookbook](https://docs.python.org/3/howto/logging-cookbook.html)
- [JSON Lines](https://jsonlines.org/)

- Walkthrough index: [Return to the walkthrough index](index.md)
- Previous chapter: [Chapter 9: How To Extend Halcyn](09-how-to-extend-halcyn.md)
- Next chapter: [Chapter 11: Common Workflows](11-common-workflows.md)
