# Chapter 7: How Bar-Wall Scenes Think

This chapter explains the bar-wall scene family in the gentlest possible way.

If you only remember one sentence, let it be this:

Bar-wall scenes are Halcyn's way of turning "a pile of values" into "a wall of
3D bars that still makes visual sense even when the data changes over time."

## Why this is harder than it sounds

Raw data is messy.

You might get:

- a neat numeric array
- nested JSON with numbers hidden inside objects and arrays
- text that is not numeric at all
- audio that changes constantly

## Stage 1: flatten the input

The first job is to collect values into one stream.

That can include:

- numbers staying numbers
- booleans becoming `1.0` or `0.0`
- strings becoming UTF-8 byte values
- nested arrays and objects being walked recursively

## Stage 2: keep some history

If you only looked at the newest values with no memory, the bar wall could
become jumpy or misleading.

So Halcyn keeps a rolling history of values.

## Stage 3: choose a useful range

The system can use:

- an automatic range inferred from recent history
- or a manual range supplied by the operator

## Stage 4: group values into buckets

If the bar wall is `N x N`, then there are `N * N` bars.

That means the source stream has to be grouped into exactly that many buckets.

## Stage 5: turn bucket intensity into geometry

Each group becomes a bar.

The normalized intensity affects things like:

- bar height
- sometimes color
- sometimes style or emphasis

## The emotional translation

If the raw input feels like chaos, the bar-wall pipeline's job is to turn that
chaos into a shape that still feels readable to a human.

That is why there is so much emphasis on:

- flattening
- history
- normalization
- grouping

Without those steps, the bars would often be technically correct but visually
unhelpful.

## Formal references for this chapter

- [Bar-wall scene guide](../site/spectrograph-suite.html)
- [Field reference](../site/field-reference.html)

## Helpful external references

- [Python statistics module](https://docs.python.org/3/library/statistics.html)
- [UTF-8 encoding docs](https://docs.python.org/3/library/stdtypes.html#str.encode)
- [JSON docs](https://docs.python.org/3/library/json.html)

Walkthrough index: [Return to the walkthrough index](README.md)  
Previous chapter: [Chapter 6: Visualizer Studio as a Daily Driver](06-visualizer-studio-as-a-daily-driver.md)  
Next chapter: [Chapter 8: The Safety Net](08-the-safety-net.md)
