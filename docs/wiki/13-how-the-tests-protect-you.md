# Chapter 13: How the Tests Protect You

If you are new to testing, it can feel like tests exist only to scold you.

In Halcyn, the better way to think about them is:

tests keep the project honest while you change it.

## There are several safety nets, not one

Halcyn uses:

- linting
- type checking
- unit tests
- coverage checks
- native build and test runs
- docs and repository contract checks

Each one catches a different kind of mistake.

## What contract tests are doing

Some tests are not about one function returning one value.

Some are about promises between files:

- a script still uses the same argument names as the code it launches
- a docs page still points at the right file
- a frontend still expects DOM ids that really exist
- a wiki page set still has the expected chapters and links

Those are contract tests, and they catch a surprising number of real regressions.

## Why coverage matters, but not in a silly way

Coverage is not a trophy.

It is a clue about how much of the code your tests actually exercised.

High coverage is helpful because it means the tests touched more of the project.
It is not helpful if you chase 100% by writing brittle nonsense.

## A good beginner testing habit

Whenever you change behavior, ask:

- "Which existing test should now change?"
- "If none should change, do I need a new one?"

That question keeps code and expectations aligned.

## Try this now

1. Find one small test file.
2. Read a test name aloud in plain language.
3. Ask what promise that test is protecting.

That turns tests from scary code into readable intent.

## Formal references for this chapter

- [Testing guide](https://gedrocht.github.io/Halcyn/testing.html)
- [Code docs guide](https://gedrocht.github.io/Halcyn/code-docs.html)

## Helpful external references

- [Python unittest documentation](https://docs.python.org/3/library/unittest.html)
- [Coverage.py documentation](https://coverage.readthedocs.io/)
- [CTest documentation](https://cmake.org/cmake/help/latest/manual/ctest.1.html)

- Walkthrough index: [Return to the walkthrough index](index.md)
- Previous chapter: [Chapter 12: Troubleshooting Without Panic](12-troubleshooting-without-panic.md)
- Next chapter: [Chapter 14: How the Browser and Desktop Tools Share the Work](14-how-the-tools-fit-together.md)
