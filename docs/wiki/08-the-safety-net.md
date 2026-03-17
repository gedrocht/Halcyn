# Chapter 8: The Safety Net

Sooner or later, every learner asks some version of:

"How do I know this thing is okay?"

This chapter is about the parts of Halcyn that answer that question.

## The API safety net

The API helps because it separates health, validation, and apply.

That means you can ask:

- is the app alive?
- is this scene valid?
- what are the runtime limits?
- what do the logs say?

without immediately changing the active scene.

## The logging safety net

The shared activity journal exists so that you do not have to guess which tool
did what.

The Activity Monitor turns that shared log into something easier to read:

- sortable
- filterable
- cross-app

## The testing safety net

The repo has several layers of checks:

- linting
- type checking
- unit tests
- coverage checks
- C++ builds and native tests
- formatting checks
- CI on GitHub
- CodeQL

## The local "am I okay?" command

If you want one strong local confidence check, use:

```powershell
.\scripts\run-all-quality-checks.ps1 -Configuration Debug
```

## GitHub as a second opinion

Local success is good.

GitHub gives you another environment and another opinion.

That matters because:

- machines differ
- paths differ
- fresh checkout behavior matters
- CI catches "works on my machine" mistakes

## Formal references for this chapter

- [Testing guide](../site/testing.html)
- [API reference](../site/api.html)
- [Control Center guide](../site/control-center.html)

## Helpful external references

- [unittest documentation](https://docs.python.org/3/library/unittest.html)
- [coverage.py documentation](https://coverage.readthedocs.io/)
- [GitHub Actions documentation](https://docs.github.com/actions)
- [CodeQL documentation](https://docs.github.com/code-security/code-scanning/introduction-to-code-scanning/about-code-scanning-with-codeql)

Walkthrough index: [Return to the walkthrough index](README.md)  
Previous chapter: [Chapter 7: How Bar-Wall Scenes Think](07-how-bar-wall-scenes-think.md)  
Next chapter: [Chapter 9: How To Extend Halcyn](09-how-to-extend-halcyn.md)
