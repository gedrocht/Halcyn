# Chapter 4: Scene JSON Without Fear

Many projects become intimidating the moment you meet the data format.

So let us make this part feel smaller.

## What scene JSON is really doing

Scene JSON is not "mysterious renderer language."

It is just a structured description of:

- what kind of scene this is
- what data belongs to the scene
- what optional presentation choices should be used

## Two broad families

### Preset-style 2D and 3D scenes

These are the scenes that feel more like ordinary graphics scenes.

### Bar-wall scenes

These scenes still become ordinary 3D geometry, but the geometry is built from
incoming data.

## What a beginner should look for first

When you open a scene JSON preview, do not try to understand every field at
once.

Look for these first:

- the scene type
- the broad family of content
- how many vertices or bars are implied
- whether render-style options are present

## Validation is your friend

If a scene fails validation, that does not mean you are "bad at JSON."

It usually means one of these:

- a required field is missing
- a value type is wrong
- a numeric range is invalid
- the payload is too large
- the shape of the data does not match the scene family

## Why strings can still matter

One of Halcyn's more approachable ideas is that strings can still become
numeric input.

When a tool converts text into UTF-8 byte values, even plain text can become a
visual signal.

## A good beginner exercise

Open a preview JSON and do only these three things:

1. identify the scene family
2. find one part that clearly came from your source data
3. find one part that is clearly about presentation or rendering choice

That is enough. You do not need to decode the entire payload at once.

## Formal references for this chapter

- [Field reference](../site/field-reference.html)
- [Bar-wall scene guide](../site/spectrograph-suite.html)
- [Scene Studio guide](../site/scene-studio.html)

## Helpful external references

- [JSON module docs](https://docs.python.org/3/library/json.html)
- [UTF-8 encoding with str.encode](https://docs.python.org/3/library/stdtypes.html#str.encode)
- [nlohmann/json API](https://nlohmann.github.io/json/api/basic_json/)

Walkthrough index: [Return to the walkthrough index](README.md)  
Previous chapter: [Chapter 3: Follow One Scene](03-follow-one-scene.md)  
Next chapter: [Chapter 5: Browser Tools in Plain Language](05-browser-tools-in-plain-language.md)
