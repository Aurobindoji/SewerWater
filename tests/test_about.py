"""About and the app's own updates (user decisions 10-Nov-2026): versions compared, GitHub's latest release read,
the setup downloaded and matched against GitHub's SHA-256 - a file that does not match is deleted, never run."""
import hashlib
import io
import json
import os

import pytest

from launcher import about as A


def test_versions():
    assert A.version_tuple("v0.9.1") == (0, 9, 1) and A.version_tuple("0.10 (beta)") == (0, 10)
    assert A.newer("v0.9.2", "0.9.1") and A.newer("0.10.0", "0.9.9") and A.newer("1.0", "0.9.9")
    assert not A.newer("0.9.1", "0.9.1") and not A.newer("0.9", "0.9.0") and not A.newer("v0.9.0", "0.9.1")


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


def test_latest_and_check(monkeypatch):
    rel = {"tag_name": "v99.0.0", "html_url": "https://github.com/x/releases/tag/v99.0.0", "body": "notes",
           "assets": [{"name": "SewerWater_Setup_99.0.0.exe", "browser_download_url": "https://x/s.exe", "size": 3,
                       "digest": "sha256:" + "a" * 64}]}
    monkeypatch.setattr(A.urllib.request, "urlopen", lambda req, timeout=0: _Resp(json.dumps(rel).encode()))
    r = A.check()
    assert r["ok"] and r["newer"] and r["latest"] == "99.0.0" and r["current"] == A.APP_VERSION
    assert r["setup"] == {"name": "SewerWater_Setup_99.0.0.exe", "url": "https://x/s.exe", "size": 3, "sha256": "a" * 64}

    def down(req, timeout=0):
        raise OSError("offline")
    monkeypatch.setattr(A.urllib.request, "urlopen", down)
    r = A.check()
    assert not r["ok"] and "internet" in r["log"]


def test_download_is_matched(tmp_path, monkeypatch):
    data = b"setup bytes"
    monkeypatch.setattr(A.urllib.request, "urlopen", lambda req, timeout=0: _Resp(data))
    good = {"name": "SewerWater_Setup_9.9.9.exe", "url": "https://x/s.exe", "size": len(data),
            "sha256": hashlib.sha256(data).hexdigest()}
    seen = []
    p = A.download(good, str(tmp_path), progress=lambda d, s: seen.append((d, s)))
    assert open(p, "rb").read() == data and seen[-1] == (len(data), len(data))
    bad = dict(good, sha256="0" * 64)
    with pytest.raises(ValueError):
        A.download(bad, str(tmp_path / "b"))
    assert os.listdir(tmp_path / "b") == []                      # the file that did not match is gone
    with pytest.raises(ValueError):
        A.download(dict(good, sha256=""), str(tmp_path / "c"))  # no SHA-256 from GitHub: no update


def test_about_page():
    h = A.about_html(master=r"D:\Data", desktop=True)
    assert A.APP_VERSION in h and "GPL" in h and "Claude" in h and "Aurobindoji" in h and r"D:\Data" in h
