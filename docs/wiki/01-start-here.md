# Chapter 1: Start Here

This chapter answers the first question that usually matters:

"What *is* Halcyn, in ordinary human language?"

## The big-picture answer

Halcyn is a program that draws scenes.

But in practice, it is more helpful to think of it as a small system with one
main job and several helper tools around that job.

The main job is:

- take scene data
- make sure the data is valid
- remember the newest valid scene
- draw that scene in a native window using the GPU

Everything else in the project exists to make that job easier to do, easier to
inspect, easier to test, and easier to learn.

## A simpler mental model

Imagine Halcyn as a stage production.

- The **Visualizer** is the stage crew that actually turns instructions into a
  visible show.
- **Visualizer Studio** is the operator console where you decide what should be
  shown next.
- The **Control Center** is the browser dashboard that helps you build, test,
  inspect, and launch things.
- The **Activity Monitor** is the shared live notebook that tells you what all
  the pieces are doing.
- **Scene Studio** is a browser-side sketchbook for preset-driven experiments.

That is the first important idea:

Halcyn is not "just the renderer" and it is not "just the tools." It is one
renderer surrounded by tools that help people use it safely.

## What you can do with it

Today, the unified Visualizer can render two broad scene families:

- classic preset-driven 2D and 3D scenes
- bar-wall scenes, where incoming data becomes a grid of colored 3D bars

That means you can use Halcyn in at least two different moods:

- as a scene viewer/editor for more traditional geometry-driven visuals
- as a data-driven visualizer where numbers, text, or audio become moving bars

## The quickest "I want to see something working" path

If you want the easiest supported setup, run:

```powershell
.\scripts\launch-visualizer-workbench.ps1
```

That opens the main working set for you:

- the native Visualizer
- the browser Control Center
- the native Visualizer Studio

From there, you can also open the Activity Monitor.

## What success looks like

When Halcyn is "working," the important signs are:

- the Visualizer window opens
- Visualizer Studio can preview and apply scenes
- the Control Center can talk to the API
- the Activity Monitor shows log entries
- `.\scripts\run-all-quality-checks.ps1 -Configuration Debug` finishes cleanly

Notice what is *not* on that list:

- knowing every file name
- understanding every OpenGL detail
- memorizing the whole repo

You can be successful with Halcyn long before you know everything.

## Where the project starts and ends

At the start, Halcyn accepts input such as:

- JSON scene descriptions
- plain text that becomes byte values
- random numeric streams
- pointer movement
- optional live audio

At the end, Halcyn produces:

- pixels in a desktop window
- logs about what happened
- test/build results that tell you whether the system is healthy

That input-to-output journey is the core story of the whole project.

## If you only remember three things from this chapter

1. Halcyn is one renderer surrounded by helper tools, not a random pile of apps.
2. The renderer's job is to turn valid scene data into pixels.
3. The easiest supported starting point is still
   `.\scripts\launch-visualizer-workbench.ps1`.

## Try this now

If you want this chapter to become real instead of theoretical:

1. Open a PowerShell window in the repo.
2. Run `.\scripts\report-prerequisites.ps1`.
3. Run `.\scripts\launch-visualizer-workbench.ps1`.
4. Confirm that you can see at least the Visualizer window and one operator tool.

## If you want the formal version of this chapter

Use these pages when you want the more compact, reference-style version:

- [Docs overview](https://gedrocht.github.io/Halcyn/index.html)
- [Tutorial](https://gedrocht.github.io/Halcyn/tutorial.html)
- [Repository README](https://github.com/gedrocht/Halcyn/blob/main/README.md)

## Helpful external references

- [PowerShell documentation](https://learn.microsoft.com/powershell/)
- [Python documentation](https://docs.python.org/3/)
- [CMake documentation](https://cmake.org/documentation/)

- Walkthrough index: [Return to the walkthrough index](index.md)
- Previous chapter: [Walkthrough index](index.md)
- Next chapter: [Chapter 2: Meet the Cast](02-meet-the-cast.md)
