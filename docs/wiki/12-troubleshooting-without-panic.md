# Chapter 12: Troubleshooting Without Panic

This chapter is not about becoming fearless.

It is about giving fear less power by making the next step obvious.

## First rule: turn mystery into evidence

When something goes wrong, gather three things:

- the command you ran
- the exact error message
- the closest matching event in the Activity Monitor

That alone changes "it is broken" into "this specific step failed."

## Second rule: shrink the problem

Ask:

- does preview work?
- does validation work?
- does apply work?
- does the renderer already have a valid scene?

Each answer removes part of the pipeline from suspicion.

## Third rule: read the failure at the right layer

Different failures belong to different layers:

- script failures
  - usually environment or launch problems
- API validation failures
  - usually malformed or unsupported scene data
- renderer problems
  - usually scene content, draw state, or visual interpretation issues
- UI problems
  - usually local control state, layout, or bridge behavior

## A tiny recovery pattern

If you are overwhelmed, do this in order:

1. stop live streaming
2. go back to a known-good example scene
3. apply it once
4. confirm the renderer is healthy again
5. reintroduce your change one small step at a time

## Good questions to ask yourself

- "What is the first thing that is definitely still working?"
- "What is the first thing that is definitely no longer working?"
- "Which one log entry changed at the same time as the visible problem?"

## One reassuring truth

A lot of debugging is not brilliance.

It is careful narrowing.

That is good news, because careful narrowing is a learnable skill.

## Formal references for this chapter

- [Testing guide](https://gedrocht.github.io/Halcyn/testing.html)
- [API guide](https://gedrocht.github.io/Halcyn/api.html)
- [Control Center guide](https://gedrocht.github.io/Halcyn/control-center.html)

- Walkthrough index: [Return to the walkthrough index](index.md)
- Previous chapter: [Chapter 11: Common Workflows](11-common-workflows.md)
- Next chapter: [Chapter 13: How the Tests Protect You](13-how-the-tests-protect-you.md)
