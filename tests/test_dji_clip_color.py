import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.mp4_fixtures import color_gamma_mp4

import dji_clip_color as dji


class ParseColorGammaTests(unittest.TestCase):
    def test_reads_d_log2_from_quicktime_keys(self):
        mp4 = color_gamma_mp4("D-Log2")
        self.assertEqual(dji.gamma_from_mp4(mp4), "D-Log2")
        self.assertEqual(dji.color_label(mp4), "D-Log2")

    def test_maps_known_gamma_strings(self):
        cases = [
            ("Rec.709", "Rec.709"),
            ("Rec.2100 HLG", "Rec.2100 HLG"),
            ("D-Log", "D-Log"),
            ("D-Log2", "D-Log2"),
            ("D-Log M", "D-Log M"),
            ("  D-Log2  ", "D-Log2"),
            ("D-LogM", "D-Log M"),
            ("DLogM", "D-Log M"),
        ]
        for raw, expected in cases:
            self.assertEqual(dji.normalize_gamma(raw), expected, raw)

    def test_unknown_gamma_is_none(self):
        self.assertIsNone(dji.normalize_gamma("Rec.2020"))
        self.assertIsNone(dji.normalize_gamma(""))

    def test_finds_keys_when_only_the_moov_tail_is_present(self):
        full = color_gamma_mp4("D-Log2", pad_mdat=4096)
        tail = full[-2048:]
        self.assertEqual(dji.color_label(tail), "D-Log2")

    def test_finds_keys_when_cover_art_pushes_moov_start_out_of_the_tail(self):
        # Real 4K takes can put a >2 MiB cover-art ilst before Keys. The gamma
        # keys+ilst still sit in the last few hundred bytes.
        full = color_gamma_mp4("Rec.709", pad_before_meta=8192)
        tail = full[-600:]
        self.assertNotIn(b"moov", tail)
        self.assertEqual(dji.color_label(tail), "Rec.709")

    def test_missing_keys_is_not_a_color(self):
        empty = b"\x00\x00\x00\x10ftypisomisom"
        self.assertIsNone(dji.gamma_from_mp4(empty))
        self.assertIsNone(dji.color_label(empty))

    def test_reads_from_file_tail_not_whole_file(self):
        mp4 = color_gamma_mp4("D-Log2", pad_mdat=4096)
        handle, path = tempfile.mkstemp(suffix=".MP4")
        os.close(handle)
        try:
            with open(path, "wb") as fh:
                fh.write(mp4)
            self.assertEqual(dji.color_label_from_file(path), "D-Log2")
        finally:
            os.remove(path)


class ProxyPathTests(unittest.TestCase):
    def test_lrf_xrf_lrv_are_proxies(self):
        self.assertTrue(dji.is_proxy_path("DCIM/DJI_001/clip.LRF"))
        self.assertTrue(dji.is_proxy_path("DCIM/CAM_001/clip.XRF"))
        self.assertTrue(dji.is_proxy_path("clip.lrv"))

    def test_original_mp4_mov_are_not_proxies(self):
        self.assertFalse(dji.is_proxy_path("DCIM/DJI_001/DJI_x_D.MP4"))
        self.assertFalse(dji.is_proxy_path("/media/take.MOV"))

    def test_shot_color_ignores_proxy_even_when_keys_say_rec709(self):
        rec709 = color_gamma_mp4("Rec.709")
        self.assertIsNone(
            dji.shot_color(rec709, "DCIM/DJI_001/clip.LRF"),
            "LRF ColorGammaSxS is Rec.709 even on a D-Log2 take",
        )
        self.assertEqual(
            dji.shot_color(rec709, "DCIM/DJI_001/clip.MP4"),
            "Rec.709",
        )


class StampPlanTests(unittest.TestCase):
    def test_log2_gets_custom_column_and_orange_clip_color(self):
        plan = dji.stamp_plan("D-Log2")
        self.assertEqual(plan.metadata_key, "DJI Color")
        self.assertEqual(plan.metadata_value, "D-Log2")
        self.assertEqual(plan.clip_color, "Orange")
        self.assertEqual(plan.input_color_space, "DJI D-Gamut")
        self.assertEqual(plan.input_gamma, "Rec.709")

    def test_d_log_is_navy_d_log_m_pink_hlg_teal(self):
        self.assertEqual(dji.stamp_plan("D-Log").clip_color, "Navy")
        self.assertEqual(dji.stamp_plan("D-Log M").clip_color, "Pink")
        self.assertEqual(dji.stamp_plan("Rec.2100 HLG").clip_color, "Teal")
        self.assertNotEqual(
            dji.stamp_plan("D-Log").clip_color,
            dji.stamp_plan("D-Log2").clip_color,
        )

    def test_rec709_stamps_metadata_but_does_not_recolor_the_clip(self):
        plan = dji.stamp_plan("Rec.709")
        self.assertEqual(plan.metadata_value, "Rec.709")
        self.assertIsNone(plan.clip_color)

    def test_d_log_maps_to_resolve_dji_d_gamut_and_d_log(self):
        plan = dji.stamp_plan("D-Log")
        self.assertEqual(plan.input_combined, "DJI D-Gamut/D-Log")
        self.assertEqual(plan.input_color_space, "DJI D-Gamut")
        self.assertEqual(plan.input_gamma, "DJI D-Log")

    def test_hlg_maps_to_rec2100_hlg(self):
        plan = dji.stamp_plan("Rec.2100 HLG")
        self.assertEqual(plan.input_combined, "Rec.2100 HLG")
        self.assertEqual(plan.input_color_space, "Rec.2020")
        self.assertEqual(plan.input_gamma, "Rec.2100 HLG")

    def test_d_log_m_is_not_tagged_as_dji_d_log(self):
        plan = dji.stamp_plan("D-Log M")
        self.assertEqual(plan.input_combined, "Rec.709")
        self.assertEqual(plan.input_gamma, "Rec.709")
        self.assertIn("D-Log M", plan.input_note)

    def test_d_log2_does_not_pretend_to_be_d_log(self):
        plan = dji.stamp_plan("D-Log2")
        self.assertEqual(plan.input_color_space, "DJI D-Gamut")
        self.assertEqual(plan.input_gamma, "Rec.709")
        self.assertNotEqual(plan.input_gamma, "DJI D-Log")
        self.assertIn("D-Log2", plan.input_note)


class FakeClip(object):
    def __init__(self, path, name="clip", third_party=True):
        self._props = {"File Path": path, "Clip Name": name}
        self.metadata = {}
        self.third_party = {}
        self.clip_color = ""
        self._third_party = third_party

    def GetName(self):
        return self._props["Clip Name"]

    def GetMetadata(self, key=None):
        if key is None:
            return dict(self.metadata)
        return self.metadata.get(key, "")

    def GetClipProperty(self, key=None):
        if key is None:
            return dict(self._props)
        return self._props.get(key, "")

    def SetThirdPartyMetadata(self, key, value):
        if not self._third_party:
            raise AttributeError("SetThirdPartyMetadata")
        self.third_party[key] = value
        return True

    def SetMetadata(self, key, value):
        self.metadata[key] = value
        return True

    def SetClipProperty(self, key, value):
        self._props[key] = value
        if key == "Clip Color":
            self.clip_color = value
        return True


class ProcessClipTests(unittest.TestCase):
    def _write(self, gamma, suffix=".MP4"):
        handle, path = tempfile.mkstemp(suffix=suffix)
        os.close(handle)
        with open(path, "wb") as fh:
            fh.write(color_gamma_mp4(gamma, pad_mdat=64))
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        return path

    def test_stamps_d_log2_onto_selected_clip(self):
        path = self._write("D-Log2")
        clip = FakeClip(path, name="DJI_001")
        result = dji.process_clip(clip)
        self.assertEqual(result.status, "stamped")
        self.assertEqual(result.label, "D-Log2")
        self.assertEqual(clip.third_party["DJI Color"], "D-Log2")
        self.assertEqual(clip.metadata.get("Color Space Notes"), "D-Log2")
        self.assertEqual(clip.metadata.get("Keywords"), "D-Log2")
        self.assertEqual(clip.clip_color, "Orange")
        self.assertEqual(clip.GetClipProperty("Input Color Space"), "DJI D-Gamut")
        self.assertEqual(clip.GetClipProperty("Input Gamma"), "Rec.709")

    def test_d_log_sets_input_color_space_and_gamma(self):
        path = self._write("D-Log")
        clip = FakeClip(path, name="log")
        project = FakeProject([])
        result = dji.process_clip(clip, project)
        self.assertEqual(result.status, "stamped")
        self.assertEqual(clip.GetClipProperty("Input Color Space"), "DJI D-Gamut/D-Log")
        self.assertEqual(clip.GetClipProperty("Input Gamma"), "DJI D-Log")
        self.assertEqual(project.GetSetting("separateColorSpaceAndGamma"), "1")

    def test_rec709_does_not_set_clip_color(self):
        path = self._write("Rec.709")
        clip = FakeClip(path)
        dji.process_clip(clip)
        self.assertEqual(clip.third_party["DJI Color"], "Rec.709")
        self.assertEqual(clip.clip_color, "")

    def test_proxy_extension_is_skipped(self):
        path = self._write("Rec.709", suffix=".LRF")
        clip = FakeClip(path, name="proxy")
        result = dji.process_clip(clip)
        self.assertEqual(result.status, "skipped")
        self.assertIn("proxy", result.detail.lower())
        self.assertEqual(clip.third_party, {})

    def test_missing_file_is_skipped(self):
        clip = FakeClip("/no/such/clip.MP4", name="offline")
        result = dji.process_clip(clip)
        self.assertEqual(result.status, "skipped")
        self.assertEqual(clip.third_party, {})

    def test_falls_back_to_keywords_when_third_party_metadata_is_missing(self):
        path = self._write("D-Log")
        clip = FakeClip(path, third_party=False)
        result = dji.process_clip(clip)
        self.assertEqual(result.status, "stamped")
        self.assertEqual(clip.metadata.get("Keywords"), "D-Log")
        self.assertEqual(clip.clip_color, "Navy")

    def test_process_clips_summarizes_a_mixed_selection(self):
        log2 = FakeClip(self._write("D-Log2"), name="a")
        proxy = FakeClip(self._write("Rec.709", suffix=".LRF"), name="b")
        report = dji.process_clips([log2, proxy])
        self.assertEqual(report.stamped, 1)
        self.assertEqual(report.skipped, 1)
        self.assertEqual(report.counts.get("D-Log2"), 1)

    def test_run_requires_a_media_pool_selection(self):
        report = dji.run(None)
        self.assertTrue(report.error)
        self.assertEqual(report.stamped, 0)

    def test_run_stamps_selected_resolve_clips(self):
        path = self._write("D-Log2")
        clip = FakeClip(path, name="sel")
        resolve = FakeResolve([clip])
        report = dji.run(resolve)
        self.assertIsNone(report.error)
        self.assertEqual(report.stamped, 1)
        self.assertEqual(clip.third_party["DJI Color"], "D-Log2")

    def test_write_with_color_management_toggles_yrgb_then_restores(self):
        project = FakeProject([])
        seen = []

        def callback():
            seen.append(project.GetSetting("colorScienceMode"))
            return "ok"

        result, toggled, original = dji.write_with_color_management(project, callback)
        self.assertEqual(result, "ok")
        self.assertTrue(toggled)
        self.assertEqual(original, "davinciYRGB")
        self.assertEqual(seen, ["davinciYRGBColorManagedv2"])
        self.assertEqual(project.GetSetting("colorScienceMode"), "davinciYRGB")
        self.assertEqual(project.GetSetting("separateColorSpaceAndGamma"), "1")

    def test_write_with_color_management_leaves_managed_projects_alone(self):
        project = FakeProject([], science="davinciYRGBColorManagedv2")
        seen = []

        def callback():
            seen.append(project.GetSetting("colorScienceMode"))
            return None

        result, toggled, original = dji.write_with_color_management(project, callback)
        self.assertFalse(toggled)
        self.assertEqual(seen, ["davinciYRGBColorManagedv2"])
        self.assertEqual(project.GetSetting("colorScienceMode"), "davinciYRGBColorManagedv2")
        self.assertEqual(project.GetSetting("separateColorSpaceAndGamma"), "1")

    def test_format_report_lists_counts_and_skips(self):
        log2 = FakeClip(self._write("D-Log2"), name="a")
        proxy = FakeClip(self._write("Rec.709", suffix=".LRF"), name="b")
        text = dji.format_report(dji.process_clips([log2, proxy]))
        self.assertIn("D-Log2", text)
        self.assertIn("proxy", text.lower())
        self.assertIn("DJI Color", text)
        self.assertIn("Orange", text)
        self.assertIn("Navy", text)


@unittest.skipUnless(
    os.path.isfile("/Users/eriksutton/Downloads/temp_video_for_share 4.mp4"),
    "local Pocket share clip not present",
)
class RealPocketTakesTests(unittest.TestCase):
    def test_share_clip_4_is_d_log2(self):
        path = "/Users/eriksutton/Downloads/temp_video_for_share 4.mp4"
        self.assertEqual(dji.color_label_from_file(path), "D-Log2")

    def test_share_clip_2_is_d_log(self):
        path = "/Users/eriksutton/Downloads/temp_video_for_share 2.mp4"
        if not os.path.isfile(path):
            self.skipTest("D-Log share clip not present")
        self.assertEqual(dji.color_label_from_file(path), "D-Log")

    def test_exif_style_rec709_take_from_the_other_body(self):
        path = "/Users/eriksutton/Downloads/DJI_20260824172956_0023_D.MP4"
        if not os.path.isfile(path):
            self.skipTest("Rec.709 take not present")
        self.assertEqual(dji.color_label_from_file(path), "Rec.709")

    def test_large_moov_rec709_take_still_reads_from_file_tail(self):
        path = "/Users/eriksutton/Downloads/DJI_20260824174438_0025_D.MP4"
        if not os.path.isfile(path):
            self.skipTest("16GB Rec.709 take not present")
        self.assertEqual(dji.color_label_from_file(path), "Rec.709")


class FakeFolder(object):
    def GetClipList(self):
        return []


class FakePool(object):
    def __init__(self, clips):
        self._clips = clips

    def GetSelectedClips(self):
        return self._clips

    def GetCurrentFolder(self):
        return FakeFolder()


class FakeProject(object):
    def __init__(self, clips, science="davinciYRGB"):
        self._pool = FakePool(clips)
        self.settings = {
            "colorScienceMode": science,
            "separateColorSpaceAndGamma": "0",
        }

    def GetMediaPool(self):
        return self._pool

    def GetSetting(self, key):
        return self.settings.get(key, "")

    def SetSetting(self, key, value):
        self.settings[key] = value
        return True


class FakeProjectManager(object):
    def __init__(self, project):
        self._project = project

    def GetCurrentProject(self):
        return self._project


class FakeResolve(object):
    def __init__(self, clips):
        self._pm = FakeProjectManager(FakeProject(clips))

    def GetProjectManager(self):
        return self._pm


if __name__ == "__main__":
    unittest.main()
