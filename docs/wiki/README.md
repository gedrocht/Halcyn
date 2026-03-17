# Halcyn Walkthrough Wiki

This is the GitHub-readable version of the "learn it like a guided video
series" layer of Halcyn's documentation.

If you want the hosted wiki home page, start with [index.md](index.md). That is
the page the wiki framework uses as its landing page.

The main docs site at [the Halcyn Pages home](https://gedrocht.github.io/Halcyn/index.html)
is already strong at being a reference manual. This walkthrough is trying to do
a different job:

- explain the project in a calmer, more human order
- start with "what is this thing?" before "what is every field?"
- connect the moving parts into one story
- give you a study path from beginner to advanced

If the formal docs are the engineer's manual, this wiki is the long-form
walkthrough that sits beside it and says, "Let's slow down and make the whole
system feel understandable."

## How to use this guide

You do not need to read every page in one sitting.

If you are brand new, read the chapters in order.

If you already know the basics, jump straight to the chapter whose question
matches your question:

- "What is Halcyn, really?"
  - [Chapter 1: Start Here](01-start-here.md)
- "What are all these apps and folders?"
  - [Chapter 2: Meet the Cast](02-meet-the-cast.md)
- "What actually happens between JSON and pixels?"
  - [Chapter 3: Follow One Scene](03-follow-one-scene.md)
- "How do I stop being scared of the scene format?"
  - [Chapter 4: Scene JSON Without Fear](04-scene-json-without-fear.md)
- "Which browser tools do what?"
  - [Chapter 5: Browser Tools in Plain Language](05-browser-tools-in-plain-language.md)
- "How does the desktop app fit in?"
  - [Chapter 6: Visualizer Studio as a Daily Driver](06-visualizer-studio-as-a-daily-driver.md)
- "How do the bar-wall scenes actually think about data?"
  - [Chapter 7: How Bar-Wall Scenes Think](07-how-bar-wall-scenes-think.md)
- "How do I reason about the API, logs, tests, and quality gates?"
  - [Chapter 8: The Safety Net](08-the-safety-net.md)
- "How do I change Halcyn without getting lost?"
  - [Chapter 9: How To Extend Halcyn](09-how-to-extend-halcyn.md)
- "How do I read the shared logs without feeling overwhelmed?"
  - [Chapter 10: How To Read the Activity Monitor](10-how-to-read-the-activity-monitor.md)
- "What are the common day-to-day workflows?"
  - [Chapter 11: Common Workflows](11-common-workflows.md)
- "How do I troubleshoot calmly when something goes wrong?"
  - [Chapter 12: Troubleshooting Without Panic](12-troubleshooting-without-panic.md)
- "How do the tests and checks actually protect me?"
  - [Chapter 13: How the Tests Protect You](13-how-the-tests-protect-you.md)
- "Why are there both browser and desktop tools?"
  - [Chapter 14: How the Browser and Desktop Tools Share the Work](14-how-the-tools-fit-together.md)
- "How do I build features with confidence instead of guessing?"
  - [Chapter 15: Building Features With Confidence](15-building-features-with-confidence.md)

Helpful appendices:

- "I need a calm dictionary of the project words."
  - [Appendix A: Glossary](appendix-glossary.md)
- "I just want a guided first hour."
  - [Appendix B: Your First Hour With Halcyn](appendix-first-hour.md)
- "I need the short command list."
  - [Appendix C: Command Cheat Sheet](appendix-command-cheat-sheet.md)
- "I do not know which app I should open."
  - [Appendix D: Which Tool Should I Open?](appendix-which-tool-should-i-open.md)

## What this wiki assumes

Very little.

It assumes:

- you can open a terminal
- you can run a PowerShell script
- you are willing to learn names one layer at a time

It does not assume:

- that you already know C++
- that you already know OpenGL
- that you already know HTTP APIs
- that you already know why the project has both browser tools and desktop tools

## The shortest possible summary

Halcyn is one renderer plus a collection of operator tools around it.

The renderer is the thing that turns validated scene data into pixels.

The surrounding tools help you:

- generate scene data
- validate it
- send it to the renderer
- inspect logs
- run checks
- learn what the system is doing

## Keep the formal docs nearby

This walkthrough is intentionally narrative. When you want the precise
field-by-field or endpoint-by-endpoint view, keep these pages nearby:

- [Docs overview](https://gedrocht.github.io/Halcyn/index.html)
- [Tutorial](https://gedrocht.github.io/Halcyn/tutorial.html)
- [Architecture guide](https://gedrocht.github.io/Halcyn/architecture.html)
- [API reference](https://gedrocht.github.io/Halcyn/api.html)
- [Testing guide](https://gedrocht.github.io/Halcyn/testing.html)
- [Code docs guide](https://gedrocht.github.io/Halcyn/code-docs.html)
- [Repository README](https://github.com/gedrocht/Halcyn/blob/main/README.md)

## One recommended study path

1. Read [Chapter 1](01-start-here.md) and [Chapter 2](02-meet-the-cast.md).
2. Run `.\scripts\launch-visualizer-workbench.ps1`.
3. Read [Chapter 3](03-follow-one-scene.md) while the tools are open.
4. Use [Chapter 4](04-scene-json-without-fear.md) while looking at a real JSON
   preview.
5. Read [Chapter 6](06-visualizer-studio-as-a-daily-driver.md) while using
   Visualizer Studio.
6. Read [Chapter 8](08-the-safety-net.md) the first time a test fails and you
   want to know what is protecting what.

## Two reading tracks

### Track 1: absolute beginner

Read:

1. [Chapter 1](01-start-here.md)
2. [Chapter 2](02-meet-the-cast.md)
3. [Appendix A](appendix-glossary.md)
4. [Chapter 3](03-follow-one-scene.md)
5. [Appendix B](appendix-first-hour.md)

### Track 2: "I can run the tools, but I still feel lost"

Read:

1. [Chapter 3](03-follow-one-scene.md)
2. [Chapter 6](06-visualizer-studio-as-a-daily-driver.md)
3. [Chapter 7](07-how-bar-wall-scenes-think.md)
4. [Chapter 8](08-the-safety-net.md)

### Track 3: "I want to change Halcyn, but I want to do it safely"

Read:

1. [Chapter 9](09-how-to-extend-halcyn.md)
2. [Chapter 13](13-how-the-tests-protect-you.md)
3. [Chapter 14](14-how-the-tools-fit-together.md)
4. [Chapter 15](15-building-features-with-confidence.md)

## External references you may want nearby

- [C++ language reference](https://en.cppreference.com/w/cpp)
- [OpenGL Wiki](https://wikis.khronos.org/opengl/Main_Page)
- [GLFW documentation](https://www.glfw.org/documentation.html)
- [GLM API reference](https://glm.g-truc.net/0.9.9/api/index.html)
- [nlohmann/json API](https://nlohmann.github.io/json/api/basic_json/)
- [cpp-httplib repository](https://github.com/yhirose/cpp-httplib)
- [Python documentation](https://docs.python.org/3/)
- [ttkbootstrap documentation](https://ttkbootstrap.readthedocs.io/)
- [MkDocs documentation](https://www.mkdocs.org/)

- Next chapter: [Chapter 1: Start Here](01-start-here.md)
