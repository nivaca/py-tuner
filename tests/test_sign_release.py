"""La firma de los archivos de una versión (tools/sign_release.py): cada archivo y SHA256SUMS firmados, y cada
firma comprobada con solo la clave pública publicada; un archivo cambiado, o otra clave, no se comprueban. Con
una clave hecha aquí, en un GNUPGHOME de la prueba: nunca la del usuario."""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import sign_release  # noqa: E402

pytestmark = pytest.mark.skipif(not shutil.which("gpg") or sys.platform == "win32", reason="needs gpg")


def short_home(name: str) -> Path:
    """A folder for gpg under /tmp: in macOS the tmp_path of pytest is so long that the path of gpg-agent's socket
    in it passes the 104 characters the system allows, and gpg can't start its agent (it made no key)."""
    return Path(tempfile.mkdtemp(prefix=f"gpg-{name}-", dir="/tmp" if os.path.isdir("/tmp") else None)) / "home"


def make_key(home: Path, name: str) -> tuple[str, Path]:
    """A key without a passphrase in HOME: its fingerprint, and its public key exported."""
    home.mkdir(mode=0o700)
    env = sign_release.bare_env(str(home))  # (gpg's folder in the PATH: Homebrew's on macOS)
    made = subprocess.run(["gpg", "--batch", "--passphrase", "", "--quick-gen-key", f"{name} <{name}@example.org>",
                           "ed25519", "sign", "never"], env=env, capture_output=True, text=True)
    if made.returncode != 0:  # (lo que gpg dijo, para saber por qué)
        pytest.fail(f"gpg made no key ({made.returncode}): {made.stderr.strip()}")
    out = subprocess.run(["gpg", "--batch", "--with-colons", "--list-secret-keys"], env=env, check=True,
                         capture_output=True, text=True).stdout
    fpr = next(line.split(":")[9] for line in out.splitlines() if line.startswith("fpr"))
    public = home.parent / f"{name}.asc"
    public.write_bytes(subprocess.run(["gpg", "--batch", "--armor", "--export", fpr], env=env, check=True,
                                      capture_output=True).stdout)
    return fpr, public


@pytest.fixture
def keys(monkeypatch):
    home = short_home("release")
    fpr, public = make_key(home, "release")
    monkeypatch.setenv("GNUPGHOME", str(home))
    yield fpr, public
    subprocess.run(["gpgconf", "--kill", "all"], env=sign_release.bare_env(str(home)),
                   capture_output=True)
    shutil.rmtree(home.parent, ignore_errors=True)


def test_every_file_signed_and_checked(tmp_path, keys):
    fpr, public = keys
    files = []
    for name, data in (("app.whl", b"wheel"), ("app.zip", b"zip"), ("app.rpm", b"rpm")):
        (tmp_path / name).write_bytes(data)
        files.append(tmp_path / name)
    sums = tmp_path / "SHA256SUMS"
    assert sign_release.main(["--key", fpr, "--public", str(public), "--sums", str(sums), *map(str, files)]) == 0
    assert sums.read_text() == "".join(f"{hashlib.sha256(f.read_bytes()).hexdigest()}  {f.name}\n" for f in files)
    for f in files + [sums]:
        assert f.with_name(f.name + ".asc").read_text().startswith("-----BEGIN PGP SIGNATURE-----")
    assert sign_release.verify(files + [sums], public) == []
    # (a file changed after it was signed: its signature is bad)
    files[0].write_bytes(b"wheel, changed")
    (bad,) = sign_release.verify(files, public)
    assert bad.startswith("app.whl:")


def test_another_key_does_not_check(tmp_path, keys):
    """The key published must be the one that signed: with another, nothing verifies, and the release stops."""
    fpr, _public = keys
    other_home = short_home("other")
    _other_fpr, other = make_key(other_home, "other")
    (tmp_path / "app.zip").write_bytes(b"zip")
    sums = tmp_path / "SHA256SUMS"
    args = ["--key", fpr, "--public", str(other), "--sums", str(sums), str(tmp_path / "app.zip")]
    assert sign_release.main(args) == 1
    subprocess.run(["gpgconf", "--kill", "all"], env=sign_release.bare_env(str(other_home)),
                   capture_output=True)
    shutil.rmtree(other_home.parent, ignore_errors=True)


def test_missing_files_are_said(tmp_path, keys, capsys):
    fpr, public = keys
    assert sign_release.main(["--key", fpr, "--public", str(public), "--sums", str(tmp_path / "S"),
                              str(tmp_path / "nothing.zip")]) == 1
    assert "missing" in capsys.readouterr().err
