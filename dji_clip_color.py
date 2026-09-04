"""Read DJI shot color from QuickTime Keys Resolve does not import.

DJI writes Rec.709 in colr/nclx even for D-Log / D-Log2. The real profile is
QuickTime Keys ``com.dji.camera.ColorGammaSxS`` in the moov tail.

Parser ported from OpenPocketCine ``ClipColorProfile`` (Apache-2.0):
https://github.com/erik-sutton95/OpenPocketCine
"""

from __future__ import print_function

import collections
import os
import struct
import sys

GAMMA_KEY = "com.dji.camera.ColorGammaSxS"
FILE_TAIL_BYTES = 2 * 1024 * 1024
METADATA_KEY = "DJI Color"

# Resolve clip colors for log / HDR so mixed bins are visible at a glance.
# D-Log2 (warm) vs D-Log (cool) are opposite ends of Resolve's palette.
# Rec.709 is tagged in metadata only — do not overwrite an existing clip color.
CLIP_COLORS = {
    "D-Log2": "Orange",
    "D-Log": "Navy",
    "D-Log M": "Pink",
    "Rec.2100 HLG": "Teal",
}

# Resolve 21.0.4 ships DJI D-Gamut + DJI D-Log only. There is no D-Log2 CST.
# Combined string is for projects with a single Input Color Space menu;
# separate gamut/gamma is for "Use Separate Color Space and Gamma".
INPUT_TRANSFORMS = {
    "D-Log": {
        "combined": "DJI D-Gamut/D-Log",
        "color_space": "DJI D-Gamut",
        "gamma": "DJI D-Log",
        "note": None,
    },
    "Rec.709": {
        "combined": "Rec.709",
        "color_space": "Rec.709",
        "gamma": "Rec.709",
        "note": None,
    },
    "Rec.2100 HLG": {
        "combined": "Rec.2100 HLG",
        "color_space": "Rec.2020",
        "gamma": "Rec.2100 HLG",
        "note": None,
    },
    "D-Log M": {
        "combined": "Rec.709",
        "color_space": "Rec.709",
        "gamma": "Rec.709",
        "note": "D-Log M has no Resolve CST — tagged Rec.709, not DJI D-Log",
    },
    "D-Log2": {
        "combined": "DJI D-Gamut",
        "color_space": "DJI D-Gamut",
        "gamma": "Rec.709",
        "note": "Resolve has no D-Log2 CST — D-Gamut color space, Rec.709 gamma (not DJI D-Log)",
    },
}

_PROXY_EXT = frozenset((".lrf", ".lrv", ".xrf"))

_GAMMA_ALIASES = {
    "rec.709": "Rec.709",
    "rec.2100 hlg": "Rec.2100 HLG",
    "d-log": "D-Log",
    "d-log2": "D-Log2",
    "d-log m": "D-Log M",
    "d-logm": "D-Log M",
    "dlogm": "D-Log M",
}

StampPlan = collections.namedtuple(
    "StampPlan",
    (
        "metadata_key",
        "metadata_value",
        "clip_color",
        "input_combined",
        "input_color_space",
        "input_gamma",
        "input_note",
    ),
)

ClipResult = collections.namedtuple(
    "ClipResult",
    ("name", "path", "label", "status", "detail"),
)

Report = collections.namedtuple(
    "Report",
    ("results", "stamped", "skipped", "counts", "error", "color_managed"),
)

_Box = collections.namedtuple("Box", ("type", "payload", "end"))


def normalize_gamma(gamma):
    if gamma is None:
        return None
    key = gamma.strip().lower()
    if not key:
        return None
    return _GAMMA_ALIASES.get(key)


def color_label(data):
    return normalize_gamma(gamma_from_mp4(data))


def gamma_from_mp4(data):
    return keys_from_mp4(data).get(GAMMA_KEY)


def shot_color(data, path):
    if is_proxy_path(path):
        return None
    return color_label(data)


def is_proxy_path(path):
    if not path:
        return False
    ext = os.path.splitext(path)[1].lower()
    return ext in _PROXY_EXT


def color_label_from_file(path):
    data = _read_file_tail(path)
    if not data:
        return None
    return shot_color(data, path)


def stamp_plan(gamma):
    label = normalize_gamma(gamma) or gamma
    transform = INPUT_TRANSFORMS.get(label, {})
    return StampPlan(
        metadata_key=METADATA_KEY,
        metadata_value=label,
        clip_color=CLIP_COLORS.get(label),
        input_combined=transform.get("combined"),
        input_color_space=transform.get("color_space"),
        input_gamma=transform.get("gamma"),
        input_note=transform.get("note"),
    )


def clip_file_path(clip):
    path = ""
    try:
        path = clip.GetClipProperty("File Path") or ""
    except Exception:
        path = ""
    if not path:
        try:
            props = clip.GetClipProperty()
        except Exception:
            props = None
        if isinstance(props, dict):
            path = props.get("File Path") or ""
    return path


def process_clip(clip, project=None):
    name = ""
    try:
        name = clip.GetName() or ""
    except Exception:
        name = ""
    path = clip_file_path(clip)
    if not path:
        return ClipResult(name, path, None, "skipped", "no file path")
    if is_proxy_path(path):
        return ClipResult(
            name,
            path,
            None,
            "skipped",
            "proxy sidecar (LRF/XRF/LRV) — import the original take",
        )
    if not os.path.isfile(path):
        return ClipResult(name, path, None, "skipped", "file not found")
    label = color_label_from_file(path)
    if not label:
        return ClipResult(
            name,
            path,
            None,
            "skipped",
            "no com.dji.camera.ColorGammaSxS in the moov tail",
        )
    plan = stamp_plan(label)
    if not apply_stamp(clip, plan, project):
        return ClipResult(name, path, label, "skipped", "Resolve refused metadata write")
    return ClipResult(name, path, label, "stamped", label)


def apply_stamp(clip, plan, project=None):
    wrote = _write_third_party(clip, plan.metadata_key, plan.metadata_value)
    wrote = _write_visible_label(clip, plan.metadata_value) or wrote
    if not wrote:
        wrote = _write_keywords(clip, plan.metadata_value)
    if plan.clip_color:
        _set_clip_property(clip, "Clip Color", plan.clip_color)
    apply_input_transform(clip, plan, project)
    return wrote


def _write_visible_label(clip, label):
    """Built-in fields that show up in Media Pool Customize Columns."""
    ok = False
    if _set_metadata(clip, "Color Space Notes", label):
        ok = True
    existing = _get_metadata(clip, "Keywords") or ""
    parts = [part.strip() for part in existing.split(",") if part.strip()]
    if label not in parts:
        parts.append(label)
        if _set_metadata(clip, "Keywords", ", ".join(parts)):
            ok = True
    return ok


def apply_input_transform(clip, plan, project=None):
    """Set Input Color Space and Input Gamma.

    DJI D-Log gamma only sticks if we write the combined IDT
    ``DJI D-Gamut/D-Log`` while separateColorSpaceAndGamma is off, then
    turn separate on. A direct Input Gamma write is ignored (Resolve 21).
    """
    if not plan.input_color_space and not plan.input_gamma and not plan.input_combined:
        return None
    if plan.input_combined and plan.input_gamma == "DJI D-Log":
        _set_project_setting(project, "separateColorSpaceAndGamma", "0")
        ok = _set_clip_property(clip, "Input Color Space", plan.input_combined)
        _set_project_setting(project, "separateColorSpaceAndGamma", "1")
        _set_clip_property(clip, "Input Gamma", plan.input_gamma)
        return plan.input_combined if ok else None
    ok_cs = False
    if plan.input_color_space:
        ok_cs = _set_clip_property(clip, "Input Color Space", plan.input_color_space)
        if not ok_cs and plan.input_combined:
            ok_cs = _set_clip_property(clip, "Input Color Space", plan.input_combined)
    if plan.input_gamma:
        _set_clip_property(clip, "Input Gamma", plan.input_gamma)
    if ok_cs:
        return plan.input_color_space or plan.input_combined
    return None


def process_clips(clips, project=None):
    # D-Log first: combined IDT + separate toggle. Other labels after so a
    # later D-Log write does not skip them.
    dlog = []
    rest = []
    for clip in clips:
        path = clip_file_path(clip)
        label = None
        if path and os.path.isfile(path) and not is_proxy_path(path):
            label = color_label_from_file(path)
        if label == "D-Log":
            dlog.append(clip)
        else:
            rest.append(clip)
    results = [process_clip(clip, project) for clip in dlog]
    results.extend(process_clip(clip, project) for clip in rest)
    stamped = 0
    skipped = 0
    counts = {}
    for result in results:
        if result.status == "stamped":
            stamped += 1
            counts[result.label] = counts.get(result.label, 0) + 1
        else:
            skipped += 1
    return Report(results, stamped, skipped, counts, None, None)


def selected_clips(resolve):
    if resolve is None:
        return [], "Run this from DaVinci Resolve: Workspace > Scripts."
    try:
        project = resolve.GetProjectManager().GetCurrentProject()
    except Exception:
        project = None
    if not project:
        return [], "Open a project first."
    try:
        pool = project.GetMediaPool()
    except Exception:
        pool = None
    if not pool:
        return [], "No media pool."
    clips = []
    try:
        getter = getattr(pool, "GetSelectedClips", None)
        if callable(getter):
            clips = getter() or []
    except Exception:
        clips = []
    if not clips:
        return [], (
            "Select clips in the Media Pool, then run "
            "Workspace > Scripts > DJI Clip Color."
        )
    return clips, None


def run(resolve):
    clips, error = selected_clips(resolve)
    project = current_project(resolve)
    managed = _mode_is_managed(_color_science_mode(project))
    if error:
        return Report([], 0, 0, {}, error, managed)

    def _stamp():
        return process_clips(clips, project)

    report, _toggled, _orig = write_with_color_management(project, _stamp)
    return Report(
        report.results,
        report.stamped,
        report.skipped,
        report.counts,
        None,
        managed,
    )


def current_project(resolve):
    if resolve is None:
        return None
    try:
        return resolve.GetProjectManager().GetCurrentProject()
    except Exception:
        return None


def project_is_color_managed(resolve):
    return _mode_is_managed(_color_science_mode(current_project(resolve)))


# Project Color Management keys the ICS write may mutate. Snapshot before
# tagging, restore after. D-Log still needs a temporary separate-on write.
_COLOR_MANAGEMENT_KEYS = (
    "colorScienceMode",
    "separateColorSpaceAndGamma",
    "isAutoColorManage",
    "rcmPresetMode",
    "colorSpaceInput",
    "colorSpaceInputGamma",
    "colorSpaceTimeline",
    "colorSpaceTimelineGamma",
    "colorSpaceOutput",
    "colorSpaceOutputGamma",
    "useCATransform",
    "inputDRT",
    "outputDRT",
    "disableFusionToneMapping",
)

# Science / auto / separate first so timeline and output strings apply in
# the original mode. A second restore pass covers Resolve rewriting them
# when the separate checkbox flips.
_COLOR_MANAGEMENT_RESTORE_ORDER = (
    "colorScienceMode",
    "isAutoColorManage",
    "rcmPresetMode",
    "separateColorSpaceAndGamma",
    "colorSpaceInput",
    "colorSpaceInputGamma",
    "colorSpaceTimeline",
    "colorSpaceTimelineGamma",
    "colorSpaceOutput",
    "colorSpaceOutputGamma",
    "useCATransform",
    "inputDRT",
    "outputDRT",
    "disableFusionToneMapping",
)


def write_with_color_management(project, callback):
    """Input Color Space / Gamma can only be written while Color Managed is on.

    Flip YRGB → Color Managed for the write, then restore Color Science and
    the rest of project Color Management. D-Log gamma is applied by writing
    the combined IDT with separateColorSpaceAndGamma off, then turning
    separate on for the gamma write. That checkbox is restored afterward.
    """
    snapshot = _snapshot_color_management(project)
    original = snapshot.get("colorScienceMode") or _color_science_mode(project)
    toggled = False
    setter = getattr(project, "SetSetting", None) if project is not None else None
    if callable(setter) and original and not _mode_is_managed(original):
        try:
            if setter("colorScienceMode", "davinciYRGBColorManagedv2"):
                toggled = True
        except Exception:
            toggled = False
    try:
        result = callback()
        return result, toggled, original
    finally:
        _restore_color_management(project, snapshot)


def _snapshot_color_management(project):
    if project is None:
        return {}
    getter = getattr(project, "GetSetting", None)
    if not callable(getter):
        return {}
    snapshot = {}
    dumped = None
    for args in ((), (None,), ("",)):
        try:
            dumped = getter(*args)
        except TypeError:
            continue
        except Exception:
            dumped = None
            break
        else:
            break
    if isinstance(dumped, dict):
        for key, value in dumped.items():
            if _is_color_management_key(key):
                snapshot[key] = value
        return snapshot
    for key in _COLOR_MANAGEMENT_KEYS:
        try:
            snapshot[key] = getter(key)
        except Exception:
            continue
    return snapshot


def _is_color_management_key(key):
    if key in _COLOR_MANAGEMENT_KEYS:
        return True
    lowered = str(key or "").lower()
    needles = (
        "colorscience",
        "colorspace",
        "colormanag",
        "separatecolor",
        "autocolor",
        "rcm",
        "aces",
        "inputdrt",
        "outputdrt",
        "catransform",
        "fusiontonemapping",
    )
    for needle in needles:
        if needle in lowered:
            return True
    return False


def _restore_color_management(project, snapshot):
    if project is None or not snapshot:
        return
    ordered = list(_COLOR_MANAGEMENT_RESTORE_ORDER)
    extras = [key for key in snapshot if key not in ordered]
    extras.sort()
    keys = ordered + extras
    for _ in (0, 1):
        for key in keys:
            if key not in snapshot:
                continue
            value = snapshot[key]
            if _get_project_setting(project, key) == value:
                continue
            _set_project_setting(project, key, value)


def _color_science_mode(project):
    if project is None:
        return ""
    try:
        getter = getattr(project, "GetSetting", None)
        if not callable(getter):
            return ""
        return getter("colorScienceMode") or ""
    except Exception:
        return ""


def _mode_is_managed(mode):
    lowered = str(mode or "").lower()
    return "colormanaged" in lowered or lowered.startswith("aces")


def format_report(report):
    if report.error:
        return report.error
    lines = []
    if report.stamped:
        parts = []
        for label in sorted(report.counts.keys()):
            parts.append("%d %s" % (report.counts[label], label))
        lines.append("Stamped %d clip(s): %s." % (report.stamped, ", ".join(parts)))
    else:
        lines.append("No clips stamped.")
    if report.skipped:
        lines.append("Skipped %d." % report.skipped)
        for result in report.results:
            if result.status == "stamped":
                continue
            name = result.name or os.path.basename(result.path or "") or "(unnamed)"
            lines.append("  %s — %s" % (name, result.detail))
    lines.extend(
        [
            "",
            "Look for Color Space Notes or Keywords in Customize Columns (search notes / keyword — DJI Color is not a built-in column).",
            "Clip colors: Orange D-Log2 · Navy D-Log · Pink D-Log M · Teal HLG.",
            "Rec.709 is tagged in DJI Color only, so existing clip colors stay put.",
            "Input Color Space / Gamma: D-Log → DJI D-Gamut + DJI D-Log; D-Log2 → DJI D-Gamut + Rec.709; HLG → Rec.2020 + Rec.2100 HLG.",
        ]
    )
    if report.counts.get("D-Log2"):
        lines.append(
            "D-Log2: D-Gamut color space, Rec.709 gamma (Resolve has no D-Log2 CST)."
        )
    if report.counts.get("D-Log M"):
        lines.append(
            "D-Log M: tagged Rec.709 (it is not DJI D-Log)."
        )
    if report.color_managed is False:
        lines.append(
            "Project is DaVinci YRGB. Input Color Space was written by briefly switching to Color Managed; project Color Management is restored afterward."
        )
    return "\n".join(lines)


def show_report(report, fusion=None, bmd=None, fu=None):
    text = format_report(report)
    print(text)
    host = fu or fusion
    if host is None or bmd is None:
        return
    try:
        _show_fusion_dialog(host, bmd, text)
    except Exception as exc:
        print("DJI Clip Color UI failed: %s" % exc)


def get_resolve():
    existing = globals().get("resolve")
    if existing is not None:
        return existing
    try:
        import DaVinciResolveScript as dvr

        return dvr.scriptapp("Resolve")
    except Exception:
        return None


def script_main(resolve=None, fusion=None, bmd=None, fu=None):
    if resolve is None:
        resolve = get_resolve()
    report = run(resolve)
    show_report(
        report,
        fusion=fusion if fusion is not None else globals().get("fusion"),
        bmd=bmd if bmd is not None else globals().get("bmd"),
        fu=fu if fu is not None else globals().get("fu"),
    )
    return report


def _show_fusion_dialog(fu, bmd, text):
    ui = fu.UIManager
    dispatcher = bmd.UIDispatcher(ui)
    window = dispatcher.AddWindow(
        {
            "ID": "DJIClipColorWin",
            "WindowTitle": "DJI Clip Color",
            "Geometry": [120, 120, 560, 380],
        },
        [
            ui.VGroup(
                {"Spacing": 10, "Weight": 1},
                [
                    ui.TextEdit(
                        {
                            "ID": "Report",
                            "Text": text,
                            "ReadOnly": True,
                            "Weight": 1,
                        }
                    ),
                    ui.Button({"ID": "CloseButton", "Text": "Close", "Weight": 0}),
                ],
            )
        ],
    )

    def _close(_ev):
        dispatcher.ExitLoop()

    window.On.CloseButton.Clicked = _close
    window.On.DJIClipColorWin.Close = _close
    window.Show()
    dispatcher.EnterLoop()
    window.Hide()


def _write_third_party(clip, key, value):
    try:
        fn = getattr(clip, "SetThirdPartyMetadata", None)
        if not callable(fn):
            return False
        return bool(fn(key, value))
    except Exception:
        return False


def _write_keywords(clip, value):
    return _set_metadata(clip, "Keywords", value)


def _set_metadata(clip, key, value):
    try:
        return bool(clip.SetMetadata(key, value))
    except Exception:
        return False


def _get_metadata(clip, key):
    try:
        getter = getattr(clip, "GetMetadata", None)
        if not callable(getter):
            return ""
        value = getter(key)
        return value if value else ""
    except Exception:
        return ""


def _set_clip_property(clip, key, value):
    try:
        return bool(clip.SetClipProperty(key, value))
    except Exception:
        return False


def _get_project_setting(project, key):
    if project is None:
        return ""
    try:
        getter = getattr(project, "GetSetting", None)
        if not callable(getter):
            return ""
        value = getter(key)
        return "" if value is None else value
    except Exception:
        return ""


def _set_project_setting(project, key, value):
    if project is None:
        return False
    try:
        setter = getattr(project, "SetSetting", None)
        if not callable(setter):
            return False
        return bool(setter(key, value))
    except Exception:
        return False


def keys_from_mp4(data):
    found = {}
    _visit(data, 0, len(data), 0, found)
    if GAMMA_KEY in found:
        return found
    moov = _find_type(data, "moov")
    if moov is not None:
        _visit(data, moov.payload, moov.end, 0, found)
    if GAMMA_KEY not in found:
        _parse_trailing_keys_ilst(data, found)
    return found


def _read_file_tail(path):
    try:
        size = os.path.getsize(path)
    except OSError:
        return None
    if size <= 0:
        return None
    start = size - FILE_TAIL_BYTES if size > FILE_TAIL_BYTES else 0
    try:
        with open(path, "rb") as fh:
            fh.seek(start)
            return fh.read()
    except OSError:
        return None


def _visit(data, start, end, depth, found):
    if depth >= 12 or GAMMA_KEY in found:
        return
    offset = start
    names = []
    while offset + 8 <= end:
        box = _next_box(data, offset, end)
        if box is None:
            break
        if box.type == "keys":
            names = _parse_keys(data, box.payload, box.end)
        elif box.type == "ilst" and (box.end - box.payload) < 8192:
            values = _parse_ilst(data, box.payload, box.end)
            for index, value in values.items():
                if 1 <= index <= len(names):
                    found[names[index - 1]] = value
        elif box.type in ("moov", "udta"):
            _visit(data, box.payload, box.end, depth + 1, found)
        elif box.type == "meta":
            _visit(data, box.payload, box.end, depth + 1, found)
            if GAMMA_KEY not in found and box.payload + 4 < box.end:
                _visit(data, box.payload + 4, box.end, depth + 1, found)
        if GAMMA_KEY in found:
            return
        offset = box.end


def _find_type(data, type_name):
    needle = type_name.encode("ascii")
    if len(needle) != 4 or len(data) < 8:
        return None
    i = 0
    limit = len(data)
    while i + 8 <= limit:
        if data[i + 4 : i + 8] == needle:
            box = _next_box(data, i, limit)
            if box is not None and box.type == type_name:
                return box
        i += 1
    return None


def _next_box(data, offset, limit):
    if offset + 8 > limit:
        return None
    size32 = _u32(data, offset)
    type_name = _fourcc(data, offset + 4)
    header = 8
    size = size32
    if size32 == 1:
        if offset + 16 > limit:
            return None
        wide = _u64(data, offset + 8)
        if wide > limit:
            return None
        size = wide
        header = 16
    elif size32 == 0:
        size = limit - offset
    if size < header or offset + size > limit:
        return None
    return _Box(type_name, offset + header, offset + size)


def _parse_keys(data, payload, end):
    if payload + 8 > end:
        return []
    count = _u32(data, payload + 4)
    if count < 1 or count > 64:
        return []
    offset = payload + 8
    names = []
    for _ in range(count):
        if offset + 8 > end:
            break
        size = _u32(data, offset)
        if size < 8 or offset + size > end:
            break
        names.append(_decode(data[offset + 8 : offset + size]))
        offset += size
    return names


def _parse_ilst(data, payload, end):
    values = {}
    offset = payload
    while offset + 8 <= end:
        box = _next_box(data, offset, end)
        if box is None:
            break
        index = _u32(data, box.payload - 4)
        child = box.payload
        while child + 8 <= box.end:
            data_box = _next_box(data, child, box.end)
            if data_box is None:
                break
            if data_box.type == "data" and data_box.end - data_box.payload >= 8:
                raw = data[data_box.payload + 8 : data_box.end]
                values[index] = _decode(raw.rstrip(b"\x00"))
                break
            child = data_box.end
        offset = box.end
    return values


def _u32(data, offset):
    return struct.unpack_from(">I", data, offset)[0]


def _u64(data, offset):
    return struct.unpack_from(">Q", data, offset)[0]


def _fourcc(data, offset):
    try:
        return data[offset : offset + 4].decode("ascii")
    except UnicodeDecodeError:
        return data[offset : offset + 4].decode("latin-1")


def _decode(raw):
    return raw.decode("utf-8", "replace")


def _parse_trailing_keys_ilst(data, found):
    """Cover-art `ilst` can push `moov` start out of a 2 MiB tail.

    DJI still writes ColorGammaSxS in a small keys+ilst pair at EOF. Walk
    backwards for a `keys` box that lists the gamma key, then its `ilst`.
    """
    end = len(data)
    needle = b"keys"
    while True:
        index = data.rfind(needle, 0, end)
        if index < 4:
            return
        box = _next_box(data, index - 4, len(data))
        if (
            box is not None
            and box.type == "keys"
            and box.payload == index + 4
        ):
            names = _parse_keys(data, box.payload, box.end)
            if GAMMA_KEY in names:
                sibling = _next_box(data, box.end, len(data))
                if sibling is not None and sibling.type == "ilst":
                    values = _parse_ilst(data, sibling.payload, sibling.end)
                    for item_index, value in values.items():
                        if 1 <= item_index <= len(names):
                            found[names[item_index - 1]] = value
                    return
        end = index


def _cli_or_script():
    resolve = globals().get("resolve")
    if resolve is not None:
        script_main(
            resolve=resolve,
            fusion=globals().get("fusion"),
            bmd=globals().get("bmd"),
            fu=globals().get("fu"),
        )
        return
    args = [arg for arg in sys.argv[1:] if not arg.startswith("-")]
    if args:
        for path in args:
            label = color_label_from_file(path)
            print("%s\t%s" % (path, label if label else "no ColorGammaSxS"))
        return
    print("Install: copy this file to Resolve's Fusion/Scripts/Utility")
    print("folder as 'DJI Clip Color.py', then Workspace > Scripts.")
    print("Or: python dji_clip_color.py clip.MP4")


# pytest imports this module as dji_clip_color. Resolve execs the installed
# copy as __main__ (or another name) with `resolve` already in globals.
if __name__ != "dji_clip_color":
    if globals().get("resolve") is not None:
        script_main(
            resolve=globals().get("resolve"),
            fusion=globals().get("fusion"),
            bmd=globals().get("bmd"),
            fu=globals().get("fu"),
        )
    elif __name__ == "__main__":
        _cli_or_script()
