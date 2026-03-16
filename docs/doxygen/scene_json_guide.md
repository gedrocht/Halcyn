# Scene JSON Guide

This page explains the JSON formats Halcyn accepts and how those JSON documents become typed scene
objects inside the application.

## Top-Level Rules

Every submitted scene must be a JSON object.

The most important required field is:

- `sceneType`
  - `"2d"` for flat 2D scenes
  - `"3d"` for perspective 3D scenes

Optional top-level fields vary by scene type, but both 2D and 3D scenes may include:

- `primitive`
  - `"points"`
  - `"lines"`
  - `"triangles"`
- `pointSize`
- `lineWidth`
- `clearColor`

Three-dimensional scenes may also include:

- `renderStyle.shader`
  - `"standard"`
  - `"neon"`
  - `"heatmap"`
- `renderStyle.antiAliasing`
  - `true`
  - `false`

## Minimal 2D Example

@code{.json}
{
  "sceneType": "2d",
  "primitive": "triangles",
  "vertices": [
    { "x": -0.5, "y": -0.5, "r": 1.0, "g": 0.0, "b": 0.0, "a": 1.0 },
    { "x":  0.0, "y":  0.5, "r": 0.0, "g": 1.0, "b": 0.0, "a": 1.0 },
    { "x":  0.5, "y": -0.5, "r": 0.0, "g": 0.0, "b": 1.0, "a": 1.0 }
  ]
}
@endcode

How Halcyn reads this:

- `sceneType` chooses `halcyn::scene_description::SceneKind::TwoDimensional`
- each object in `vertices` becomes a `halcyn::scene_description::Vertex2D`
- `primitive` becomes `halcyn::scene_description::PrimitiveType`
- validation checks that the number of vertices matches the primitive choice

## 2D Field Meanings

- `x`, `y`
  - position in 2D scene space
- `r`, `g`, `b`, `a`
  - per-vertex color channels in the range the renderer expects for OpenGL color values
- `pointSize`
  - only matters when drawing points
- `lineWidth`
  - only matters when drawing lines
- `clearColor`
  - controls the color used to clear the window each frame before drawing geometry

## Minimal 3D Example

@code{.json}
{
  "sceneType": "3d",
  "primitive": "triangles",
  "camera": {
    "position": { "x": 2.5, "y": 2.0, "z": 2.5 },
    "target":   { "x": 0.0, "y": 0.0, "z": 0.0 },
    "up":       { "x": 0.0, "y": 1.0, "z": 0.0 },
    "fovYDegrees": 60.0,
    "nearPlane": 0.1,
    "farPlane": 100.0
  },
  "vertices": [
    { "x": -0.8, "y": -0.8, "z": 0.0, "r": 1.0, "g": 0.2, "b": 0.2, "a": 1.0 },
    { "x":  0.8, "y": -0.8, "z": 0.0, "r": 0.2, "g": 1.0, "b": 0.2, "a": 1.0 },
    { "x":  0.0, "y":  0.8, "z": 0.0, "r": 0.2, "g": 0.4, "b": 1.0, "a": 1.0 }
  ]
}
@endcode

How Halcyn reads this:

- `sceneType` chooses `halcyn::scene_description::SceneKind::ThreeDimensional`
- `camera` becomes `halcyn::scene_description::Camera3D`
- each item in `vertices` becomes `halcyn::scene_description::Vertex3D`
- the renderer later turns camera data into view/projection matrices

## Indexed 3D Example

If `indices` is present, Halcyn uses indexed drawing.

@code{.json}
{
  "sceneType": "3d",
  "primitive": "triangles",
  "camera": {
    "position": { "x": 2.3, "y": 1.8, "z": 2.6 },
    "target":   { "x": 0.0, "y": 0.0, "z": 0.0 },
    "up":       { "x": 0.0, "y": 1.0, "z": 0.0 },
    "fovYDegrees": 60.0,
    "nearPlane": 0.1,
    "farPlane": 100.0
  },
  "vertices": [
    { "x": -0.8, "y": -0.8, "z": 0.0, "r": 1.0, "g": 0.2, "b": 0.2, "a": 1.0 },
    { "x":  0.8, "y": -0.8, "z": 0.0, "r": 0.2, "g": 1.0, "b": 0.2, "a": 1.0 },
    { "x":  0.0, "y":  0.8, "z": 0.0, "r": 0.2, "g": 0.4, "b": 1.0, "a": 1.0 },
    { "x":  0.0, "y":  0.0, "z": 1.2, "r": 1.0, "g": 0.9, "b": 0.2, "a": 1.0 }
  ],
  "indices": [0, 1, 2, 0, 1, 3, 1, 2, 3, 2, 0, 3]
}
@endcode

Why indices matter:

- they let the scene reuse vertices instead of duplicating them
- they match how many real 3D pipelines organize meshes
- they let Halcyn exercise both `glDrawArrays` and `glDrawElements`

## Spectrograph-Oriented 3D Example

The dedicated spectrograph renderer and desktop spectrograph control panel still
submit ordinary 3D scenes. The difference is that they tend to generate a dense
bar grid and make use of the `renderStyle` object.

@code{.json}
{
  "sceneType": "3d",
  "primitive": "triangles",
  "camera": {
    "position": { "x": 7.6, "y": 6.4, "z": 7.6 },
    "target":   { "x": 0.0, "y": 1.4, "z": 0.0 },
    "up":       { "x": 0.0, "y": 1.0, "z": 0.0 },
    "fovYDegrees": 52.0,
    "nearPlane": 0.1,
    "farPlane": 100.0
  },
  "renderStyle": {
    "shader": "heatmap",
    "antiAliasing": true
  },
  "vertices": [
    { "x": -0.32, "y": 0.0, "z": -0.32, "r": 0.08, "g": 0.25, "b": 0.86, "a": 1.0 },
    { "x":  0.32, "y": 0.0, "z": -0.32, "r": 0.08, "g": 0.25, "b": 0.86, "a": 1.0 }
  ],
  "indices": [0, 1]
}
@endcode

What the new fields mean:

- `renderStyle.shader`
  - chooses the fragment-shader presentation style rather than changing the
    mesh geometry
- `renderStyle.antiAliasing`
  - tells the renderer whether multisample anti-aliasing should stay enabled

The dedicated route `GET /api/v1/examples/spectrograph` returns a built-in
scene of this general shape.

## Validation Rules Beginners Should Know

Halcyn does not accept every syntactically valid JSON scene. It also checks semantic rules such as:

- the vertex count must make sense for the primitive type
- point size and line width must be greater than zero
- index values must not point past the end of the vertex list
- a 3D camera's `position` and `target` must not be the same point
- a 3D camera's `up` vector must not be the zero vector
- `nearPlane` must be positive
- `farPlane` must be larger than `nearPlane`
- request payload size must stay within configured limits

That is why the project distinguishes between:

- **parsing**
  - "Can this JSON be read into C++ values?"
- **validation**
  - "Do those values describe a sensible drawable scene?"

## Where To Look In Code

- `halcyn::scene_description::SceneTypes`
  - the data model the JSON maps into
- `halcyn::scene_description::SceneJsonCodec::Parse`
  - structural parsing and JSON-to-type conversion
- `halcyn::scene_description::ValidateSceneDocument`
  - semantic rules
- `halcyn::scene_description::BuildRenderScene`
  - conversion into the flattened render-friendly form
