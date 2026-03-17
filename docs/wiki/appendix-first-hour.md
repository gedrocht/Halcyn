# Appendix B: Your First Hour With Halcyn

This appendix is for the moment when you do not want theory first. You want a
guided hour.

## Minute 0 to 10: make sure the machine is ready

Run:

```powershell
.\scripts\report-prerequisites.ps1
```

What you want:

- the important tools show as found
- nothing surprising looks broken

## Minute 10 to 20: open the main working set

Run:

```powershell
.\scripts\launch-visualizer-workbench.ps1
```

What you want:

- the Visualizer opens
- Visualizer Studio opens
- the browser tool opens

## Minute 20 to 30: make one simple scene change

In Visualizer Studio:

1. choose a simple source such as plain text
2. preview the scene
3. validate it
4. apply it once

What you are learning:

- source selection
- preview
- validation
- apply

## Minute 30 to 40: try the other scene family

Still in Visualizer Studio:

1. switch from preset scene to bar-wall scene
2. preview again
3. apply again

What you are learning:

- one source can become multiple scene families
- the renderer path stays the same even when the scene family changes

## Minute 40 to 50: watch the logs

Open the Activity Monitor.

What you are looking for:

- visible log entries
- multiple tools contributing to one timeline

This is where the system often starts to feel less magical and more knowable.

## Minute 50 to 60: run the safety net

Run:

```powershell
.\scripts\run-all-quality-checks.ps1 -Configuration Debug
```

What you are learning:

- how the repo checks itself
- what "healthy" looks like

## If you only have fifteen minutes

Do just this:

1. run `.\scripts\report-prerequisites.ps1`
2. run `.\scripts\launch-visualizer-workbench.ps1`
3. preview one scene
4. apply one scene

That is already a real first contact with the project.

- Walkthrough index: [Return to the walkthrough index](index.md)
