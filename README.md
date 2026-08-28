# DJI Clip Color

**Show D-Log vs D-Log2 on DJI clips in DaVinci Resolve.**

Resolve reads DJI takes as Rec.709 even when you shot log. The camera hides the
real profile in a Keys field (`com.dji.camera.ColorGammaSxS` /
`DjiCameraColorGammaSxS`) that Resolve never maps.

Select clips → run the script → the Media Pool shows **D-Log2**, **D-Log**,
**D-Log M**, **HLG**, or **Rec.709**. Log clips also get a clip color.

![Clip color legend](docs/clip-colors.svg)

| Shot color | Clip color |
| --- | --- |
| D-Log2 | Orange |
| D-Log | Navy |
| D-Log M | Pink |
| Rec.2100 HLG | Teal |
| Rec.709 | metadata only |

Orange vs navy so a mixed bin is obvious at thumbnail size.

## Install

**Mac** (double-click `install.command` after unzipping, or):

```bash
curl -fsSL https://raw.githubusercontent.com/erik-sutton95/dji-clip-color/main/install.sh | bash
```

**Windows** (double-click `install.bat` after unzipping, or PowerShell):

```powershell
irm https://raw.githubusercontent.com/erik-sutton95/dji-clip-color/main/install.ps1 | iex
```

Restart Resolve if it is already open.

Step-by-step, skipped-clip table, and uninstall: **[user guide](docs/user-guide.md)**.

## Use

1. Import **original** MP4 / MOV takes (not `.LRF` / `.XRF` / `.LRV` proxies).
2. Select them in the Media Pool.
3. **Workspace → Scripts → DJI Clip Color**.
4. Right-click a column header and enable **DJI Color**.

## Input Color Space / Gamma

The script also writes Resolve’s clip Input Color Space and Input Gamma when
the project is **DaVinci YRGB Color Managed** (otherwise the API silently
refuses):

| Shot color | Input Color Space | Input Gamma |
| --- | --- | --- |
| D-Log | DJI D-Gamut | DJI D-Log |
| Rec.2100 HLG | Rec.2020 | Rec.2100 HLG |
| Rec.709 / D-Log M | Rec.709 | Rec.709 |
| D-Log2 | DJI D-Gamut | Rec.709 |

Resolve 21 still has **no D-Log2 CST**. Those clips are labeled Orange / DJI
Color only — we do not fake them as DJI D-Log.

## Probe a file

```bash
python3 dji_clip_color.py clip.MP4
```

## License

Apache-2.0. Parser ported from
[OpenPocketCine](https://github.com/erik-sutton95/OpenPocketCine) `ClipColorProfile`.
