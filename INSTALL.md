# Installing and Running Halcyn on Windows

## Recommended setup

For the smoothest experience, keep the repository on a local drive such as:

```text
C:\Users\user\Documents\GitHub\Halcyn
```

Running from a network-backed path can trigger extra PowerShell trust prompts and Git safe-directory checks during dependency downloads.

## Required tools

- CMake
- Python 3
- `python -m pip install jinja2`
- Git
- one C++ toolchain:
  - recommended: Visual Studio 2022 with `Desktop development with C++`
  - alternative: Ninja plus a working compiler

## Optional tools

- Doxygen for generated code docs
- clang-format for formatting

## First build

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\report-prerequisites.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\build-halcyn-app.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\run-native-tests.ps1
```

## Running the app

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\launch-halcyn-app.ps1
```

## Running the browser Control Center

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\launch-browser-control-center.ps1
```

## Troubleshooting

### PowerShell asks whether scripts are trusted

If the repository is on a network-backed path, PowerShell may keep warning even after `Unblock-File`.

Use:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\report-prerequisites.ps1
```

The most reliable fix is to move the repository to a local drive.

### Git reports dubious ownership during CMake dependency downloads

This is common on network-backed paths because CMake clones dependencies into `build/`.

Workarounds:

- preferred: move the repository to a local drive
- temporary: trust all Git directories on this machine

```powershell
git config --global --add safe.directory '*'
```

Only use the broad Git trust setting if you are comfortable trusting repositories on this machine.

### `cl.exe` appears as missing in `report-prerequisites.ps1`

That usually means `cl.exe` is not on PATH in the current shell. If Visual Studio 2022 is detected and CMake identifies MSVC during configure, the toolchain is working.
