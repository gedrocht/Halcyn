# Appendix A: Glossary

This appendix is a calm dictionary for the project words you will keep seeing.

## Visualizer

The native C++ application that actually renders scenes and opens the graphics
window.

## Visualizer Studio

The unified native desktop operator app that helps you choose sources, build
scenes, preview them, validate them, and send them to the Visualizer.

## Control Center

The browser dashboard for setup, builds, tests, docs, process orchestration,
and API inspection.

## Activity Monitor

The sortable, filterable browser view of the shared activity journal written by
the participating apps.

## Scene Studio

The browser-side scene-authoring companion, especially helpful for preset-style
experiments.

## Scene

The structured description of what the renderer should draw.

## Scene JSON

The JSON representation of a scene that tools can preview, validate, and send
over HTTP.

## Validate

Check whether a scene is acceptable without replacing the currently active
scene.

## Apply

Send a valid scene to become the new active scene.

## Scene store

The runtime-owned source of truth for the current active scene.

## JSON codec

The layer that translates between JSON text and the project's internal scene
structures.

## Bar-wall scene

A data-driven 3D scene family where incoming values become a grid of bars.

## Rolling history

A recent window of past values that helps automatic normalization stay useful
instead of reacting only to the newest sample.

## Normalization

The process of mapping raw values into a more useful active range so they can
be displayed consistently.

## Shared activity journal

The common log stream that multiple Halcyn tools write into so the Activity
Monitor can display one timeline.

## Coverage

A measure of how much code was exercised while the tests ran.

## Workbench

A convenience launcher that opens the main pieces together so you can start
working without manually launching each one.

Walkthrough index: [Return to the walkthrough index](README.md)
