# Chapter 15: Building Features With Confidence

This chapter is about making changes in a way that future-you can still trust.

## A calm sequence for non-trivial work

1. Explain the change in plain language first.
2. Find the smallest owning layer.
3. Read the nearby tests and docs.
4. Make the smallest coherent code change.
5. Update docs and comments while the reasoning is still fresh.
6. Add or update tests.
7. Run the narrowest checks first, then the wider suite.

This sequence works because it keeps you from editing blindly.

## What "smallest owning layer" means

If the problem is scene meaning, prefer the scene-description layer.

If the problem is renderer draw behavior, prefer the renderer layer.

If the problem is an operator workflow, prefer the relevant browser or desktop
tool.

That keeps changes local, which makes them easier to review and safer to ship.

## Documentation is part of the feature

In Halcyn, a change is not really finished if:

- the walkthrough now lies
- the docs site now lies
- the tests do not describe the new behavior
- the comments still explain the old logic

## One good beginner measure of completeness

Ask:

"Could somebody else understand what I changed tomorrow?"

If the answer is "not without asking me," then the work is probably not
finished yet.

## A professional habit worth stealing

Before you stop, do one explicit self-review pass looking for:

- naming that became unclear
- comments that now lie
- tests that should be more specific
- docs that still describe yesterday's workflow

That one pass catches a lot.

## Formal references for this chapter

- [Testing guide](https://gedrocht.github.io/Halcyn/testing.html)
- [Architecture guide](https://gedrocht.github.io/Halcyn/architecture.html)
- [Repository README](https://github.com/gedrocht/Halcyn/blob/main/README.md)

- Walkthrough index: [Return to the walkthrough index](index.md)
- Previous chapter: [Chapter 14: How the Browser and Desktop Tools Share the Work](14-how-the-tools-fit-together.md)
- Next chapter: [Walkthrough index](index.md)
