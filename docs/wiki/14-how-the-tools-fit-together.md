# Chapter 14: How the Browser and Desktop Tools Share the Work

Halcyn has both browser tools and desktop tools because they solve different
problems well.

That is not duplication for the sake of duplication.

## What the browser side is best at

The browser side is especially good at:

- dashboards
- documentation
- quick links
- activity viewing
- broad orchestration

That is why the Control Center and Activity Monitor live there.

## What the desktop side is best at

The desktop side is especially good at:

- richer local controls
- file dialogs
- audio device access
- operator-focused workflows that feel more like a control console

That is why Visualizer Studio lives there.

## The important unifying idea

These are not two separate products.

They are two operator surfaces around one renderer and one scene API.

That is why learning the shared pipeline matters more than memorizing the UI
layout of one particular tool.

## A mental shortcut

If you are unsure which tool owns a job, ask:

- "Is this mainly about seeing and orchestrating the system?"
  - browser side
- "Is this mainly about locally shaping and sending data?"
  - desktop side

## Where they meet

They meet at shared concepts:

- scene JSON
- API routes
- logs
- examples
- tests
- docs

That shared middle is what keeps Halcyn coherent instead of feeling like a pile
of unrelated apps.

## Formal references for this chapter

- [Control Center guide](https://gedrocht.github.io/Halcyn/control-center.html)
- [Scene Studio guide](https://gedrocht.github.io/Halcyn/scene-studio.html)
- [Visualizer Studio guide](https://gedrocht.github.io/Halcyn/desktop-control-panel.html)
- [Architecture guide](https://gedrocht.github.io/Halcyn/architecture.html)

- Walkthrough index: [Return to the walkthrough index](index.md)
- Previous chapter: [Chapter 13: How the Tests Protect You](13-how-the-tests-protect-you.md)
- Next chapter: [Chapter 15: Building Features With Confidence](15-building-features-with-confidence.md)
