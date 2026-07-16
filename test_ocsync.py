import argparse
import importlib.machinery
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path

loader = importlib.machinery.SourceFileLoader("ocsync", str(Path(__file__).with_name("ocsync")))
spec = importlib.util.spec_from_loader(loader.name, loader)
ocsync = importlib.util.module_from_spec(spec)
loader.exec_module(ocsync)


class OcsyncTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.previous_dir = ocsync.OC_DIR
        self.previous_data = ocsync.DATA_DIR
        self.previous_state = ocsync.STATE_DIR
        self.previous_private = ocsync.PRIVATE_KEY
        self.previous_public = ocsync.PUBLIC_KEY
        ocsync.OC_DIR = self.root / "config"
        ocsync.DATA_DIR = self.root / "data"
        ocsync.STATE_DIR = self.root / "state"
        ocsync.PRIVATE_KEY = ocsync.STATE_DIR / "identity.pem"
        ocsync.PUBLIC_KEY = ocsync.STATE_DIR / "identity.pub.pem"
        ocsync.OC_DIR.mkdir(parents=True)

    def tearDown(self):
        ocsync.OC_DIR = self.previous_dir
        ocsync.DATA_DIR = self.previous_data
        ocsync.STATE_DIR = self.previous_state
        ocsync.PRIVATE_KEY = self.previous_private
        ocsync.PUBLIC_KEY = self.previous_public
        self.tmp.cleanup()

    def test_profile_selection_rejects_unknown_and_removed_values(self):
        self.assertEqual(ocsync.profile_names("core,omo"), ("core", "omo"))
        self.assertEqual(set(ocsync.PROFILES), {"core", "omo", "plugins", "agents", "skills"})
        with self.assertRaises(ValueError):
            ocsync.profile_names("core,secrets")
        with self.assertRaises(ValueError):
            ocsync.profile_names("core,commands")

    def test_collect_local_only_collects_requested_profile_and_skips_node_modules(self):
        (ocsync.OC_DIR / "opencode.json").write_text('{"model":"x"}')
        (ocsync.OC_DIR / "oh-my-openagent.json").write_text('{"omo":true}')
        (ocsync.OC_DIR / ".opencode/plugins").mkdir(parents=True)
        (ocsync.OC_DIR / ".opencode/plugins/plugin.js").write_text("export default {}")
        (ocsync.OC_DIR / ".opencode/plugins/node_modules").mkdir()
        (ocsync.OC_DIR / ".opencode/plugins/node_modules/nope.js").write_text("bad")
        core = ocsync.collect_local(("core",))
        self.assertEqual(set(core), {"opencode.json"})
        plugins = ocsync.collect_local(("plugins",))
        self.assertEqual(set(plugins), {".opencode/plugins/plugin.js"})

    def test_safe_relative_blocks_traversal_and_absolute_paths(self):
        self.assertTrue(ocsync.is_safe_relative("skills/foo/SKILL.md"))
        self.assertFalse(ocsync.is_safe_relative("../auth.json"))
        self.assertFalse(ocsync.is_safe_relative("/etc/passwd"))

    def test_auth_envelope_can_only_be_decrypted_by_recipient_key(self):
        if not ocsync.shutil.which("openssl"):
            self.skipTest("openssl unavailable")
        first = self.root / "first"
        second = self.root / "second"
        for path in (first, second):
            path.mkdir()
            os.chmod(path, 0o700)
        source_private, source_public = first / "private.pem", first / "public.pem"
        target_private, target_public = second / "private.pem", second / "public.pem"
        import subprocess
        for private, public in ((source_private, source_public), (target_private, target_public)):
            subprocess.run(["openssl", "genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048", "-out", str(private)], check=True, capture_output=True)
            subprocess.run(["openssl", "pkey", "-in", str(private), "-pubout", "-out", str(public)], check=True, capture_output=True)
        secret = b'{"token":"never-display"}'
        encrypted = subprocess.run(["openssl", "pkeyutl", "-encrypt", "-pubin", "-inkey", str(target_public), "-pkeyopt", "rsa_padding_mode:oaep", "-pkeyopt", "rsa_oaep_md:sha256"], input=secret, check=True, capture_output=True).stdout
        decrypted = subprocess.run(["openssl", "pkeyutl", "-decrypt", "-inkey", str(target_private), "-pkeyopt", "rsa_padding_mode:oaep", "-pkeyopt", "rsa_oaep_md:sha256"], input=encrypted, check=True, capture_output=True).stdout
        self.assertEqual(decrypted, secret)
        wrong = subprocess.run(["openssl", "pkeyutl", "-decrypt", "-inkey", str(source_private), "-pkeyopt", "rsa_padding_mode:oaep", "-pkeyopt", "rsa_oaep_md:sha256"], input=encrypted, capture_output=True)
        self.assertNotEqual(wrong.returncode, 0)


if __name__ == "__main__":
    unittest.main()
