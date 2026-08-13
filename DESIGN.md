# amigarig — design doc

## Why this exists

The current `amiga-run` script hardcodes one machine configuration, one
Workbench version, one fixed set of files to copy onto a synthesized boot
disk, and one project mount. Every variation (different CPU/chipset/
Kickstart/Workbench, different fonts or libraries per project, testing
floppy load speed, producing a release image for CI) currently means
editing the script itself. There is no reuse between "similar but not
identical" setups, and Amiga's case-insensitive, assign-based filesystem
model doesn't map cleanly onto ad hoc bash/`cp -v` calls.

`amigarig` replaces this with a small, layered configuration system
(object-oriented in spirit: profiles inherit from and override each
other) that resolves down to a single merged configuration, then:

1. builds a synthetic boot environment (directory or disk image) from a
   declarative `copy:` spec, honoring Amiga-style case-insensitive
   filename resolution and logical assigns,
2. optionally builds a project volume the same way (mounted directory,
   or a floppy/hdf image populated via `copy:`, useful for load-speed
   testing),
3. assembles an `fs-uae` command line from the merged config, and
4. runs it — or, in "build only" mode, just leaves the artifact behind
   (e.g. as a CI release step).

## Non-goals / why not Ansible

Ansible manages idempotent state on remote hosts via playbooks. This
tool is local, single-shot, and produces a flat CLI argument list plus
some throwaway files — there's no remote target, no idempotency
requirement, and Ansible's group/host var hierarchy doesn't comfortably
express multiple inheritance (`A1200-Blizzard1230-3.1` inherits both a
machine profile and a Kickstart/Workbench profile) or the
append-vs-replace list semantics this design needs. A small, purpose
built Python package is a better fit than bending Ansible to a job it
wasn't built for.

## Core concepts

### Config layers and inheritance

Every config file is a YAML mapping, optionally with an `extends:` key
(a name, or a list of names, for multiple inheritance). Files live in
named registries by directory:

```
configs/
  machine/      base, aga, ocs-ecs, a500, a1200, a1200-blizzard1230-31, ...
  kickstart/    13, 30, 31
  workbench/    wb13, wb31, wb39
  boot/         minimal, debug, baud31250
  run/          named full presets (optional convenience layer)
```

Each directory is its own **registry**: `extends: a1200` resolves by
name within the appropriate registry, not by file path. A profile can
also reference a config in a *different* registry via a dedicated key
(not `extends`) — e.g. a `kickstart` profile has a `workbench:` key
naming a workbench profile. This is how "kickstart 3.1 defaults to
Workbench 3.1, but can be overridden to 3.9 while keeping Kickstart 3.1"
works: `workbench` is a reference field resolved through the workbench
registry, independent of the kickstart's own `extends` chain.

### Merge algorithm

Given a resolved inheritance chain (parents first, most specific last),
merge pairwise, most specific wins:

- **dict + dict** → recursive deep-merge, key by key. A dict is *never*
  wholesale-replaced by a later layer just because the later layer
  mentions the same key — only the specific sub-keys it sets are
  affected. E.g. setting `copy.fonts` in a child does not disturb
  `copy.c`/`copy.libs` inherited from the parent.
- **list + list**, same key → **replace** by default (last write wins).
- **append instead of replace** → the overriding layer prefixes the key
  with `+`, e.g. `+fonts: [...]` inside a `copy:` block appends to the
  inherited `fonts` list rather than replacing it. The `+` is stripped
  before comparison; it can appear on any list-valued key at any
  nesting depth, not just inside `copy:`.
- **scalar + scalar**, same key → replace.

This one algorithm (implemented once, used for every registry: machine,
kickstart, workbench, boot, run, and project-local overrides) is the
entire "object orientation" of the system.

### Merge priority (full stack, low to high)

```
built-in defaults
  → machine chain (base → ... → specific machine)
  → kickstart chain (→ its default workbench, unless overridden)
  → workbench chain
  → boot chain (minimal → ... → specific boot profile)
  → run profile (optional named preset combining the above)
  → project-local config file (./.amigarig.yaml in cwd, if present)
  → environment variables (AMIGA_MODEL, AMIGA_WORKBENCH, AMIGA_KICKSTART,
    AMIGA_FASTRAM, ...) via a fixed name→dotted-key mapping table
  → explicit CLI flags (--set key=value, or --machine/--workbench/...)
  → positional binary + args (become the startup-sequence command line)
```

Env vars are read directly from `os.environ` — loading `.env`/`.envrc`
into the environment is direnv's job, not amigarig's.

### Assigns

Amiga-style logical assigns are a config section like any other
(`assigns:`, deep-merged, plain key = replace that assign):

```yaml
assigns:
  fsuae: "/home/boost/Data/Dokument/FS-UAE"
  wb: "fsuae:workbench3.1"
```

`boot:` is the one assign amigarig owns itself: injected at run start
once the temp dir (or image) exists, never set in a config file —
conceptually equivalent to Amiga auto-mounting `RAM:` at boot.
`project:` defaults to `$PWD` unless a run overrides it.

**Resolver** (`resolve(path, assigns) -> Path`), given a string:

1. Starts with `/` → absolute host path, used as-is, no assign lookup.
2. Otherwise split on first `:`. If the prefix is a known assign, resolve
   the assign's target recursively (assigns may point to other assigns,
   e.g. `wb:` → `fsuae:workbench3.1` → real path), then join the
   remainder onto it. Cycle-guarded (visited-set).
3. Unknown prefix before `:` → hard error (an Amiga-side typo should not
   silently become a literal relative path).
4. Once fully resolved to a real base directory, the remaining relative
   path segments are looked up case-insensitively (see below).

### Case-insensitive filesystem resolution

Amiga is case-insensitive; Linux is not; different Workbench versions
use different casing for the same logical file (`C/Copy` vs `c/copy`).
One utility handles this everywhere paths meet the real filesystem:

```python
def ci_resolve(base: Path, *components: str) -> Path | None:
    """Resolve components under base case-insensitively, one path
    segment at a time. Returns None if any segment is missing."""
```

Implementation walks one path segment at a time, listing each directory
via `os.scandir` and matching case-insensitively, caching each
directory's `{lower_name: real_name}` listing since the same WB tree is
probed repeatedly per run. This is the single choke point every copy
operation goes through — worth unit-testing in isolation (fake
filesystem / tmp_path fixtures) since it's the fiddliest piece.

### copy_types and handlers

`copy_types` defines, per logical category, a default source assign,
destination assign, and an ordered list of **handlers** — small
functions that expand one resolved (source, dest) pair into zero or
more concrete writes. This is also just config, mergeable like
everything else:

```yaml
copy_types:
  c:       { src: "wb:C",      dest: "boot:c" }                # handlers: [copy] implied
  libs:    { src: "wb:Libs",   dest: "boot:libs" }
  l:       { src: "wb:L",      dest: "boot:l" }
  devs:    { src: "wb:Devs",   dest: "boot:devs" }
  fonts:   { src: "wb:Fonts",  dest: "boot:fonts", handlers: [copy_font] }
  project: { src: "project:",  dest: "boot:",       handlers: [copy, copy_icons] }
```

Handler signature: `handler(item: ResolvedCopyItem, ctx) -> list[ResolvedCopyItem]`,
chained via flat-map in list order.

- **`copy`** (default if `handlers` omitted): the resolved item as-is —
  one source, one destination.
- **`copy_font`**: given `Garamond/9`, expands to two items: the
  `Garamond.font` file and the `Garamond/9` bitmap-size directory,
  both case-insensitively resolved.
- **`copy_icons`**: given a resolved item (arbitrary src/dest, possibly
  renamed, e.g. `src=build/bin/MyGame.exe dest=boot:MyGame`), derives
  `icon_src = <source>.info` (sibling of *source*) and, if it exists
  (checked via the same case-insensitive probe), emits a second item
  `dest = <dest>.info` (sibling of *dest*). No-op if the `.info` file
  doesn't exist.

### copy item shapes

Each entry in a `copy.<type>` list is either a bare string (source =
destination = that string, both relative to the type's default
src/dest assigns) or a mapping (Docker Compose–style) that overrides
either side independently and can point at a different assign entirely:

```yaml
copy:
  c: [CD, Echo, List, Wait, NoBorder, Copy]
  +fonts: [Garamond/9, /home/boost/amiga/fonts/Eurochart/9]
  project:
    - { source: data/levels/Level1, destination: levels/Level1 }
    - { source: build/bin/MyGame.exe, destination: MyGame }
  libs:
    - { source: "project:build/libs/music.library" }
```

A leading `normalize_copy_item()` step turns both shapes into a common
`ResolvedCopyItem`-precursor before resolution, so nothing downstream
needs to know which shape was used.

### Writers (destination backends)

Two writer backends implement the same interface
(`write(item: ResolvedCopyItem) -> None` / `finalize()`):

- **`HostDirWriter`** — writes into a real directory (the ephemeral tmp
  dir for the boot disk in normal dev-run mode, or a plain directory
  copy for a "keep as directory" release artifact).
- **`ADFVolumeWriter`** — writes into an in-memory/on-disk Amiga
  filesystem image via `amitools.fs` (`ADFSVolume`, `BlkDevFactory`,
  etc. — used as a library, not shelled out to `xdftool`). Used for
  floppy/hdf images, whether that's a `project:` floppy for load-speed
  testing or a "single disk" release build.

Which writer backs `boot:` and which backs `project:` is a per-target
config choice (see below) — the rest of the pipeline (resolution,
handlers) is identical either way.

### Disk targets: `boot` and `project`

Both `boot` and `project` are named disk targets with the same shape:

```yaml
boot:
  type: harddrive        # harddrive | floppy | hdf
  keep_as: null          # null = ephemeral tmp dir/file, deleted after run
  run: true               # false = build artifact only, skip launching fs-uae

project:
  type: harddrive         # default: mount $PWD directly, no copy needed
  # type: floppy triggers the copy_types.project pipeline into an image instead
```

- `boot.type: harddrive` + `keep_as: null` (default): today's behavior
  — plain tmp directory, `--hard_drive_0=$TMPDIR`, deleted on exit.
- `boot.type: harddrive` + `keep_as: <path>`: assemble as a directory,
  move/copy to `<path>` instead of deleting.
- `boot.type: floppy|hdf` + `keep_as: <path>` + `run: false`: build via
  `ADFVolumeWriter` straight to `<path>`, skip launching fs-uae — a CI
  release-packaging step, not a dev run.
- `project.type: harddrive` (default): `--hard_drive_1=$PWD`, no copy
  step, `copy_types.project` is unused.
- `project.type: floppy`: build a `Project`-labeled image via
  `copy_types.project`, mount as `--floppy_drive_0=...`. Since the boot
  hard drive still boots Workbench first, the floppy is auto-assigned
  `project:` by AmigaOS the same as the directory mount would have
  been — no behavior change from the C-program's point of view.
- `copy_types.project.dest` can be overridden per run to `boot:MyGame`
  instead of `boot:`, which — combined with `project.type: harddrive`
  or floppy being irrelevant — supports the "single disk" mode: project
  files copied straight onto the boot disk/image under a named folder,
  useful for producing a genuine one-disk release build.

## startup-sequence

No templating engine — the existing layering/merge machinery already
covers what would otherwise need conditionals. `boot.startup` is just
another mergeable list of AmigaDOS command lines, using the same
`+key` append rule as `copy:`:

```yaml
# configs/boot/minimal.yaml
startup:
  - "cd Project:"
  - "{binary} {args}"

# configs/boot/debug.yaml
extends: minimal
+startup: ["NoBorder"]
```

"Conditional" lines (e.g. only add `NoBorder` in debug mode) are just a
question of which profile contributes the line — a profile that
doesn't extend `debug` never sees it — the same reasoning already used
for `copy:`. There's no implicit ordering rule (e.g. "launch line is
always last"): the `"{binary} {args}"` sentinel appears wherever the
config author places it in the list, exactly like the commented-out
`Sys:Prefs/Preferences` line in the current script sits after the
launch line today.

**Rendering**: each line is passed through a plain `str.format(binary=...,
args=...)` (or manual placeholder substitution) — safe here since these
are trusted local config files, not user input. Assign-style tokens
(`Project:`) are left as literal AmigaDOS syntax; they're resolved by
AmigaOS at boot time, not by amigarig, so no assign-resolution step is
needed for startup-sequence content itself.

**Disabling the generated file entirely**: `startup: []` produces an
empty (or absent) generated `s/startup-sequence`. This is for cases
where a fully handwritten sequence is easier to maintain than composing
one from merged lines — instead supply it as a normal file via
`copy: { s: ["startup-sequence"] }` (a new `copy_types.s` entry,
`src` pointing wherever the handwritten file lives, `dest: "boot:s"`).
The copy step runs after startup-sequence generation, so if both are
present the copied file simply overwrites the generated one — no
special precedence rule needed, just document that `startup: []` is
the conventional way to signal "don't bother generating one, I'm
supplying it via copy instead."

If a real need for runtime-conditional lines (e.g. "include this line
only if `fsuae.fast_memory > 0`", not expressible as a layering choice)
shows up later, swapping `.format()` for a per-line Jinja render is a
contained change — not a reason to add the dependency now.

## Package layout

Given the number of concerns, this is a proper Python package rather
than a single script:

```
amigarig/
  __init__.py
  cli.py              # argparse entrypoint, --config/--set/env var handling, top-level flow
  config/
    __init__.py
    registry.py       # loads YAML files per directory into named registries
    merge.py          # the deep-merge + `+key` append algorithm (pure functions, no I/O)
    resolve.py         # walks extends chains + cross-registry refs (workbench:, etc.) into one merged dict
  assigns.py           # assign table + resolve() resolver (cycle-guarded)
  fsutil.py            # ci_resolve() and friends (case-insensitive filesystem walk + cache)
  copyspec.py          # normalize_copy_item(), ResolvedCopyItem dataclass, item resolution against assigns/ci_resolve
  handlers.py          # copy, copy_font, copy_icons + a name->function registry, chaining
  writers/
    __init__.py         # Writer protocol
    hostdir.py           # HostDirWriter
    adfvolume.py          # ADFVolumeWriter (wraps amitools.fs)
  disktargets.py        # boot/project target assembly: picks writer, drives copy_types + handlers, produces final path(s)
  fsuae.py              # merged config -> fs-uae argv builder (fsuae.* namespace -> --flags)
  startup.py            # startup-sequence template rendering from merged `boot.startup` lines + binary/args
  runner.py             # orchestration: resolve config -> build targets -> build argv -> exec or skip (run: false)
configs/                # checked-in default machine/kickstart/workbench/boot profiles
                         # (see registries above) -- used at dev-time via
                         # AMIGARIG_CONFIG_DIR=./configs; the live configs dir
                         # normally lives at the OS standard per-user config
                         # location, see "Configs dir location" below
tests/
  test_merge.py
  test_assigns.py
  test_fsutil.py         # case-insensitive resolution against a fake tree
  test_copyspec.py
  test_handlers.py
  test_writers_hostdir.py
  test_writers_adfvolume.py
  test_fsuae_argv.py
pyproject.toml
```

Each module is independently unit-testable without touching fs-uae or a
real Workbench tree (fake filesystems for `fsutil`/writers, plain dicts
for `merge`/`resolve`).

## CLI shape

```
amigarig --config=a1200-blizzard1230-31 [--set key=value ...] <binary> [args...]
```

- `--config=<name>` looks up a `run/` preset, or a machine profile name
  directly if no matching run preset exists (so you don't need a `run/`
  file for every combination if the machine profile alone is enough).
- `--set key=value` (repeatable) overrides any dotted config key
  directly from the CLI, highest priority short of the binary/args
  themselves.
- Positional `<binary> [args...]` becomes the startup-sequence launch
  line, same as today's script (`"$BIN" $@`).
- Env vars (`AMIGA_MODEL`, `AMIGA_WORKBENCH`, `AMIGA_KICKSTART`,
  `AMIGA_FASTRAM`, ...) sit between the project-local config file and
  `--set`/CLI flags in priority, letting direnv/.env-based per-project
  defaults work without a CLion-specific config file.

Typical CLion "External Tool" invocation:
```
Program:    amigarig
Arguments:  --config=a1200-blizzard1230-31 $TargetPath$ $Prompt$
```

## Configs dir location

The configs dir is a single directory that directly contains `local.yaml`
plus the `machine/`, `kickstart/`, `workbench/`, `boot/`, `run/`
subdirectories -- it is not a sibling of `local.yaml`, it *is* the parent
of everything.

Resolution order (via `platformdirs.user_config_dir("amigarig")`, the
maintained cross-platform equivalent of "the XDG dir on Linux"):

1. `--configs-dir=<path>` (highest priority)
2. `AMIGARIG_CONFIG_DIR` env var
3. OS standard per-user config dir -- `~/.config/amigarig` on Linux, the
   platform-correct equivalent on macOS/Windows (default)

The repo's own `configs/` directory is the checked-in, portable default
profile set (no machine-specific paths in it after the `local.yaml` layer
was introduced) -- useful for development/testing against known-good
configs, or as the seed you copy into the real configs dir on a new
machine. Point at it explicitly with `AMIGARIG_CONFIG_DIR=$(pwd)/configs`
or `--configs-dir=./configs`; day-to-day usage needs neither flag.

## local.yaml

The one file where machine-specific facts belong -- paths to your FS-UAE
install, ROM directory, Workbench trees, and the fs-uae binary itself.
Lives at `<configs-dir>/local.yaml`, merged as the **lowest**-priority
layer (below machine/workbench/kickstart/boot), so profiles stay portable
and reference these as assigns instead of hardcoding paths:

```yaml
fsuae_binary: "/usr/bin/fs-uae"
assigns:
  fsuae: "/home/boost/Data/Dokument/FS-UAE"
  kickstart: "/home/boost/Data/Amiga/kickstart"
```

A kickstart profile then references a ROM via the assign rather than a
literal path (`fsuae.kickstart_file: "kickstart:kick31.rom"`), resolved
through the same case-insensitive assign resolver used for `copy:`, just
before the fs-uae argv is built (`fsuae.resolve_fsuae_paths`, applied to
an explicit allowlist of path-like `fsuae.*` keys so option values like
`serial_port: tcp://127.0.0.1:1234` aren't misparsed as assign refs).

## Open items / follow-ups (not blocking initial build)

- Exact `amitools.fs` call sequence for creating + writing an ADF/HDF
  (lift from `amitools/tools/xdftool.py`'s command handlers rather than
  re-deriving from scratch).
- Whether `workbench-3.9` in practice should `extends: wb31` or have its
  own independent base list — depends on the real WB3.9 file layout,
  confirm against an actual tree before hardcoding the shipped default.
- Dedup rule for `+`-appended copy lists when the same logical item ends
  up listed twice (e.g. a project re-adding a font the workbench already
  ships) — dedupe by resolved (source, dest) identity at copy-execution
  time, not at merge time.
