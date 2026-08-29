# Contributing

Thanks for looking. DJI Clip Color is a small Apache-2.0 Resolve script.
PRs against `main` are welcome.

## Setup

```bash
python3 -m unittest discover -s tests -v
```

Unit tests do not need DaVinci Resolve. They cover the MP4 Keys parser,
clip-color mapping, and metadata stamping.

To try it in Resolve, run `./install.sh` (Mac/Linux) or `install.bat` (Windows)
and restart Resolve.

## Patches

- Keep personal paths, captures, and camera serials out of git.
- Prefer a failing test before parser or tagging changes.
- Match existing Python 3.6-friendly style (Resolve’s bundled Python).

Bugs and ideas: GitHub Issues. No need for a heavy process.

By contributing you agree your work is licensed under Apache-2.0, same as
the rest of this repo.
