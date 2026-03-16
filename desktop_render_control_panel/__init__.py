"""Desktop control panel for driving Halcyn scenes from a native window.

This package exists for the cases where a browser UI is not enough:

- choosing real local audio devices
- keeping a native desktop window open beside the renderer
- offering a richer "operator control surface" for previewing, validating,
  and live-streaming scene updates into the Halcyn HTTP API

The package is split into a few intentionally simple pieces:

- scene building
- audio capture and analysis
- HTTP communication
- non-visual controller logic
- the Tkinter window itself

That separation is what lets the project keep strong unit tests around a GUI
tool without needing every test to drive a real window manually.
"""
