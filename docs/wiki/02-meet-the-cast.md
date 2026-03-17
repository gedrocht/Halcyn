# Chapter 2: Meet the Cast

Now that we have the one-sentence summary, we can name the important pieces
without making them feel like a random pile of folders.

## The apps you will actually meet

### Visualizer

The Visualizer is the native C++ application that actually draws the current
scene.

It owns:

- the window
- the OpenGL context
- the rendering loop
- the embedded HTTP API
- the current scene state

If Halcyn were a concert, this is the part that actually makes sound come out
of the speakers.

### Visualizer Studio

Visualizer Studio is the unified native desktop operator app.

It is the place where you:

- choose a source
- choose a scene family
- preview the generated scene JSON
- validate the scene
- apply the scene once
- or stream updates continuously

It is not the renderer itself. It is the most hands-on operator surface for
feeding the renderer.

### Control Center

The Control Center is the browser dashboard.

It helps when your question is less "what scene do I want?" and more:

- is the environment healthy?
- can I run builds and tests?
- what docs should I read?
- what does the API return?
- is the managed app running?

### Activity Monitor

The Activity Monitor is a shared browser log viewer.

This matters because Halcyn is not one silent executable. Multiple tools can be
running at once, and you often want one place to sort and filter the timeline
of what happened.

### Scene Studio

Scene Studio is the browser-side creative companion.

It is useful when you want:

- a browser-first surface for preset-style scene experiments
- a lighter-weight creative space
- a way to author scenes without being inside the desktop app

## The source folders and what they mean

These are the folder names worth learning early.

### `src/scene_description`

This is where the project defines what a scene *means*.

It includes:

- scene types
- validation rules
- JSON encoding/decoding
- built-in example scenes

### `src/shared_runtime`

This holds shared runtime pieces such as:

- the current scene store
- logging support

### `src/http_api`

This is the API layer inside the native app.

### `src/opengl_renderer`

This is where the actual GPU-facing drawing work lives.

### `src/desktop_app`

This is the top-level glue that wires the native application together.

### `browser_control_center`

This folder contains the browser dashboard and Activity Monitor server logic.

### `browser_scene_studio`

This folder contains the browser Scene Studio app.

### `desktop_visualizer_operator_console`

This is the current supported desktop operator app: Visualizer Studio.

### `desktop_shared_control_support`

This is shared support code that multiple desktop pieces use, such as:

- activity logging
- audio helpers
- API client helpers

## Why there are old-looking folders too

You may still notice older split desktop packages in the repo.

That can feel confusing at first, so here is the plain explanation:

- some older packages still exist as internal support modules
- the supported public workflow has been unified
- the repo is allowed to keep useful helper code even after the public workflow
  becomes simpler

So "folder exists" does not always mean "this is still a user-facing app."

## Formal references for this chapter

- [Architecture guide](../site/architecture.html)
- [Control Center guide](../site/control-center.html)
- [Visualizer Studio guide](../site/desktop-control-panel.html)
- [Scene Studio guide](../site/scene-studio.html)

## Helpful external references

- [OpenGL Wiki](https://wikis.khronos.org/opengl/Main_Page)
- [GLFW documentation](https://www.glfw.org/documentation.html)
- [ttkbootstrap documentation](https://ttkbootstrap.readthedocs.io/)
- [Python http.server docs](https://docs.python.org/3/library/http.server.html)

Walkthrough index: [Return to the walkthrough index](README.md)  
Previous chapter: [Chapter 1: Start Here](01-start-here.md)  
Next chapter: [Chapter 3: Follow One Scene](03-follow-one-scene.md)
