# Chapter 9: How To Extend Halcyn

This last chapter is for the moment when you stop asking only:

"How does Halcyn work?"

and start asking:

"How do I change it without making a mess?"

## Start with the question, not the code

Before you edit anything, say the change in plain language.

Examples:

- "I want a new example scene."
- "I want a new control in Visualizer Studio."
- "I want a new API response field."
- "I want a better log message."

## A simple routing guide

If your change is about:

- scene meaning or validation
  - start in `src/scene_description`
- renderer behavior
  - start in `src/opengl_renderer`
- API endpoints
  - start in `src/http_api`
- native app wiring
  - start in `src/desktop_app`
- browser dashboard behavior
  - start in `browser_control_center`
- browser scene authoring behavior
  - start in `browser_scene_studio`
- unified desktop operator workflow
  - start in `desktop_visualizer_operator_console`

## A good beginner workflow for changes

1. Find the layer that owns the behavior.
2. Read the nearby tests first.
3. Make the smallest useful change.
4. Add or adjust tests.
5. Run the relevant focused script first.
6. Run the full quality pass after that.

## Keep the story aligned

One of the easiest ways to make a project harder to learn is to change code
without changing the explanations around it.

When you add something real, remember to update:

- tests
- docs
- comments where the logic changed
- any user-facing script or workflow text that became outdated

## Formal references for this chapter

- [Code docs guide](../site/code-docs.html)
- [Architecture guide](../site/architecture.html)
- [Testing guide](../site/testing.html)
- [Repository README](../../README.md)

## Helpful external references

- [cppreference for C++](https://en.cppreference.com/w/cpp)
- [OpenGL Wiki](https://wikis.khronos.org/opengl/Main_Page)
- [GLFW documentation](https://www.glfw.org/documentation.html)
- [Python documentation](https://docs.python.org/3/)
- [Git documentation](https://git-scm.com/doc)

Walkthrough index: [Return to the walkthrough index](README.md)  
Previous chapter: [Chapter 8: The Safety Net](08-the-safety-net.md)  
Next chapter: [Walkthrough index](README.md)
