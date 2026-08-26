# amigarig

A layered-config wrapper around `fs-uae` and `vamos` for running, testing,
and packaging classic-Amiga dev builds — replaces a pile of hardcoded
one-off `amiga-run` shell scripts with a small, composable configuration
system.

See [`DESIGN.md`](DESIGN.md) for the full architecture writeup (merge
algorithm, assigns, writers, backends, ...). This document is the
practical "what do I run" guide.

## Why

Testing an Amiga build usually means booting a synthesized disk with the
right Kickstart ROM, the right Workbench version, the right set of
`C:`/`Libs:`/`Fonts:`/etc. files, your project mounted somewhere, and your
binary launched from a startup-sequence — and that combination changes
per machine profile, per debug session, per CI job. `amigarig` resolves a
stack of small YAML profiles (machine → kickstart → workbench → boot →
run preset → project-local overrides → env vars → CLI flags) down to one
merged configuration, then:

1. builds a synthetic boot environment (a directory, or a floppy/hdf
   image) from a declarative `copy:` spec,
2. optionally builds a project volume the same way,
3. and either launches it (via `fs-uae` or `vamos`) or just leaves the
   built artifact behind.

## Install

```sh
pip install -e .
```

This installs the `amigarig` command (`amigarig.cli:main`) and pulls in
`amitools` (used as a library for ADF/HDF writing and for the `vamos`
backend), `PyYAML`, and `platformdirs`.

## Configuring

Configs live in a directory (`~/.config/amigarig` by default — see
`--configs-dir` / `AMIGARIG_CONFIG_DIR` in DESIGN.md to point elsewhere,
e.g. at this repo's own checked-in `configs/` while developing):

```
<configs-dir>/
  local.yaml          # your machine-specific paths (see below) — not checked in
  machine/             # base, aga, ocs-ecs, a500, a1200, a1200-blizzard1230-31, ...
  kickstart/            # 13, 31
  workbench/              # wb13, wb31, wb39
  boot/                    # minimal, debug
  run/                      # named presets tying machine+boot together
```

Start by copying [`configs/local.example.yaml`](configs/local.example.yaml)
to `<configs-dir>/local.yaml` and filling in real paths:

```yaml
fsuae_binary: "/usr/bin/fs-uae"
assigns:
  fsuae: "/home/you/Data/Dokument/FS-UAE"
  kickstart: "/home/you/Data/Amiga/kickstart"
```

Everything else (machine profiles, Kickstart ROM filenames, Workbench
trees, boot startup-sequences) is expressed in terms of assigns like
`fsuae:` and `kickstart:` set there, so the rest of `configs/` stays
portable across machines. This repo's own `configs/` directory is a
working example set — point at it directly during development:

```sh
export AMIGARIG_CONFIG_DIR=$(pwd)/configs
```

## Basic usage

```sh
amigarig --config=<name> [--set key=value ...] [binary [args...]]
```

- `--config=<name>` looks up a `run/` preset by that name, or falls back
  to a `machine/` profile directly if no matching preset exists.
- `--set key=value` (repeatable) overrides any dotted merged-config key,
  highest priority short of the binary itself (`--set fsuae.chip_memory=4096`).
- `binary [args...]` becomes the startup-sequence launch line — relative
  to your project directory (mounted as `project:`), e.g. `bin/game -x`.
  **Omit it entirely** to just build the configured target(s) and stop —
  see "Rig-only" below.

## Example scenarios

### 1. Run a build on a real machine profile (fs-uae)

Boot an A1200/Blizzard 1230 + Kickstart 3.1/Workbench 3.1 machine and
launch a binary from the current project:

```sh
amigarig --config=a1200-blizzard1230-31 bin/game
```

`a1200-blizzard1230-31` (`configs/machine/a1200-blizzard1230-31.yaml`)
extends `a1200` → `[aga, "31"]` → `base`, pulling in the AGA chipset
defaults, Kickstart 3.1 (and its default Workbench 3.1), and `base`'s
`copy_types`/window/serial-port defaults. `boot: {type: harddrive}` and
`project: {type: harddrive}` (both inherited from `base`) mean: assemble
an ephemeral boot directory with `C:`/`Libs:`/`Fonts:`/etc. copied in,
mount the current directory directly as `project:`, generate a
startup-sequence that `cd`s to `Project:` and runs `bin/game`, then spawn
`fs-uae`.

### 2. Named `run/` preset (machine + boot combo as one name)

`configs/run/dev.yaml`:

```yaml
machine: a1200-blizzard1230-31
boot: debug
```

```sh
amigarig --config=dev bin/game
```

`--config=dev` matches a `run/` preset name, so it resolves `machine:`
and `boot:` from the preset instead of you spelling both out every time.
`boot/debug.yaml` extends `minimal`, appends `NoBorder` to the
startup-sequence, copies in a debug-stub binary, and turns on
`fsuae.console_debugger`. Add your own `run/` presets the same way for
whatever combinations you use often.

### 3. Override machine settings ad hoc

Bump fast RAM and force NTSC without writing a new profile:

```sh
amigarig --config=a1200-blizzard1230-31 \
  --set fsuae.fast_memory=8192 \
  --set fsuae.video_standard=ntsc \
  bin/game
```

Or per-project, drop a `.amigarig.yaml` in the project root (merged in
automatically, between the boot chain and env vars) so the whole team
gets the same overrides without CLI flags:

```yaml
# ./.amigarig.yaml
fsuae:
  fast_memory: 8192
project:
  type: harddrive
```

### 4. Floppy load-speed testing

Copy the project onto an actual `.adf` floppy image instead of mounting
the directory, to test real floppy load behavior:

```yaml
# ./.amigarig.yaml
project:
  type: floppy
  volume_name: Project
copy_types:
  project: { src: "project:", dest: "project:", handlers: [copy, copy_icons] }
copy:
  project:
    - { source: "bin", destination: "bin" }
    - { source: "data", destination: "data" }
```

```sh
amigarig --config=a1200-blizzard1230-31 bin/game
```

`project.type: floppy` triggers the `copy_types.project` pipeline into an
`ADFVolumeWriter`-built image instead of a plain mount; fs-uae still
boots the `boot:` hard drive first, and AmigaOS auto-assigns `project:`
to the floppy the same as it would a directory, so nothing else changes.

### 5. One-disk release build (build only, no fs-uae)

Package project files straight onto the boot disk under a named folder
and produce a real, standalone floppy image — no launch, useful as a CI
step:

```yaml
# release.yaml (a run/ preset, or pass via --set)
machine: a1200-blizzard1230-31
boot:
  type: floppy
  keep_as: "./dist/game.adf"
  run: false
  volume_name: Game
copy_types:
  project: { src: "project:", dest: "boot:", handlers: [copy, copy_icons] }
copy:
  +project:
    - { source: "bin/game", destination: "game" }
```

```sh
amigarig --config=release bin/game
```

`boot.run: false` builds the image (via `ADFVolumeWriter`) and stops
before ever invoking a backend; `keep_as:` says where the finished `.adf`
ends up instead of a deleted tmp file. `bin/game` is still needed here
because the startup-sequence (`{binary} {args}`) is generated onto the
disk for someone booting it for real later.

### 6. Rig-only: just produce an artifact, run nothing

For the simplest case — "give me a floppy/directory with these files on
it, I'm not launching an emulator right now" — omit the binary entirely:

```yaml
# ./.amigarig.yaml
boot:
  type: floppy
  keep_as: "./dist/data-disk.adf"
  volume_name: Data
copy_types:
  project: { src: "project:", dest: "boot:", handlers: [copy, copy_icons] }
copy:
  project:
    - { source: "data", destination: "data" }
```

```sh
amigarig --config=a1200-blizzard1230-31
```

No `binary` argument → amigarig builds the configured `boot:`/`project:`
target(s), skips startup-sequence generation entirely, and stops. No
`fs-uae`, no `vamos`, nothing launched — just the artifact at
`./dist/data-disk.adf` (or wherever `keep_as:` points). This is the
"rig a floppy or directory and do nothing" mode, and works best pointed
at a single `boot.keep_as:` target rather than a split boot:/project:
setup.

### 7. Running under `vamos` instead of `fs-uae`

`vamos` (also part of `amitools`, used here as a library) emulates the
AmigaOS API surface for a single process rather than booting a whole
machine — no CPU/chipset config, no ROM, much faster to launch than
booting Workbench:

```sh
amigarig --config=a1200-blizzard1230-31 --set backend=vamos bin/game
```

or bake it into a `run/` preset:

```yaml
# configs/run/vamos-dev.yaml
machine: a1200-blizzard1230-31
backend: vamos
```

```sh
amigarig --config=vamos-dev bin/game
```

The `boot:` target is still assembled the normal way (`copy:
{c, libs, fonts, ...}`) for consistency between backends, and every
amigarig assign that resolves to a real host directory (`project:`,
`boot:`, `wb:`, ...) is exposed to vamos as an AmigaOS volume of the same
name, so `copy_types` written with fs-uae in mind resolve the same way.
Requirements/limits:

- `boot.type` must be `harddrive` — vamos maps volumes to host
  directories, not amitools disk images, so a floppy/hdf `boot:` target
  is rejected.
- Any assign backed by a floppy/hdf image is skipped (with a warning)
  rather than mapped as a volume — use `type: harddrive` for anything
  that needs to be reachable from a vamos run.
- `s/startup-sequence` is still generated (harmless) but never read —
  vamos launches `binary` directly instead of booting Workbench.
- Extra vamos-specific config passes through a `vamos:` key, deep-merged
  onto the generated vamos config, e.g. `--set vamos.process.stack=32`.

## Environment variables

`AMIGA_MODEL`, `AMIGA_WORKBENCH`, `AMIGA_KICKSTART`, `AMIGA_FASTRAM`,
`AMIGA_CHIPRAM`, `AMIGA_SLOWRAM` map onto merged-config keys (see
`ENV_VAR_MAP` in `amigarig/config/build.py`), sitting between the
project-local config file and `--set`/CLI flags in priority — handy for
direnv/`.envrc`-based per-project defaults.

## Running the tests

```sh
python -m pytest
```
