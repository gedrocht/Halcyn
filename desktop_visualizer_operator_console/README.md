# Desktop Visualizer Studio

`desktop_visualizer_operator_console` is the native desktop control surface for the
unified Halcyn Visualizer.

## What this package does

This package gives the project one desktop app that can:

- choose a live source such as JSON, plain text, random values, audio, or pointer motion
- translate that source into either a preset scene or a bar-wall scene
- preview, validate, apply, and live-stream the resulting Halcyn scene JSON
- save and reload operator settings
- write structured activity events that the browser Activity Monitor can sort and filter

## Why this package exists

Earlier iterations split desktop responsibilities across several apps. That made
it harder for a beginner to answer simple questions such as:

- "Which app should I open first?"
- "Which app actually sends the scene?"
- "Which app owns audio capture?"

The unified Visualizer Studio keeps those answers simple:

- the Visualizer renders
- the browser Control Center orchestrates builds, docs, and monitoring
- Visualizer Studio is the single native desktop operator app

## Main modules

- `visualizer_operator_console_controller.py`
  The behavior layer. It owns request payload state, audio capture coordination,
  renderer API calls, and the background live-stream loop.
- `visualizer_operator_console_window.py`
  The ttkbootstrap user interface. It owns widgets, layout, and event wiring.
- `visualizer_operator_scene_builder.py`
  The translation layer. It turns one chosen source into one scene for the
  unified Visualizer.

## External references

- [ttkbootstrap](https://ttkbootstrap.readthedocs.io/)
- [Tkinter](https://docs.python.org/3/library/tkinter.html)
- [ScrolledText](https://docs.python.org/3/library/tkinter.scrolledtext.html)
- [tkinter.filedialog](https://docs.python.org/3/library/dialog.html#tkinter.filedialog)
- [threading](https://docs.python.org/3/library/threading.html)
- [json](https://docs.python.org/3/library/json.html)
