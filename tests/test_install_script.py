from __future__ import annotations

import os
import stat
import subprocess
import tarfile
from pathlib import Path


RELEASE_VERSION = "9.9.9"
RELEASE_TARGET = "linux-arm64"


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def _create_release_archive(tmp_path: Path) -> Path:
    binary_name = f"strix-{RELEASE_VERSION}-{RELEASE_TARGET}"
    binary_path = tmp_path / binary_name
    _write_executable(binary_path, f"#!/bin/sh\nprintf 'strix {RELEASE_VERSION}\\n'\n")

    archive_path = tmp_path / f"{binary_name}.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        archive.add(binary_path, arcname=binary_name)
    return archive_path


def _create_mock_commands(tmp_path: Path) -> Path:
    mock_bin = tmp_path / "mock-bin"
    mock_bin.mkdir()
    _write_executable(
        mock_bin / "uname",
        '#!/bin/sh\n[ "$1" = "-s" ] && echo Linux || echo aarch64\n',
    )
    _write_executable(mock_bin / "docker", "#!/bin/sh\nexit 0\n")
    _write_executable(
        mock_bin / "curl",
        """#!/bin/sh
output=""
while [ "$#" -gt 0 ]; do
  if [ "$1" = "-o" ]; then
    output="$2"
    shift 2
    continue
  fi
  printf '%s\\n' "$1" >> "$STRIX_TEST_CURL_LOG"
  shift
done
cp "$STRIX_TEST_ARCHIVE" "$output"
""",
    )
    return mock_bin


def _create_installer_environment(
    tmp_path: Path,
    archive_path: Path,
    mock_bin: Path,
) -> tuple[dict[str, str], Path, Path]:
    home_path = tmp_path / "home"
    home_path.mkdir()
    curl_log_path = tmp_path / "curl.log"
    environment = os.environ.copy()
    environment.update(
        {
            "HOME": str(home_path),
            "PATH": f"{mock_bin}:/usr/bin:/bin",
            "SHELL": "/bin/bash",
            "STRIX_TEST_ARCHIVE": str(archive_path),
            "STRIX_TEST_CURL_LOG": str(curl_log_path),
            "VERSION": RELEASE_VERSION,
        }
    )
    environment.pop("GITHUB_ACTIONS", None)
    return environment, home_path, curl_log_path


def _run_installer(
    repository_root: Path,
    environment: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        ["/bin/bash", str(repository_root / "scripts/install.sh")],
        cwd=repository_root,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def test_installer_downloads_and_runs_linux_arm64_release(tmp_path: Path) -> None:
    repository_root = Path(__file__).resolve().parents[1]
    archive_path = _create_release_archive(tmp_path)
    mock_bin = _create_mock_commands(tmp_path)
    environment, home_path, curl_log_path = _create_installer_environment(
        tmp_path,
        archive_path,
        mock_bin,
    )

    result = _run_installer(repository_root, environment)

    assert result.returncode == 0, result.stderr
    expected_filename = f"strix-{RELEASE_VERSION}-{RELEASE_TARGET}.tar.gz"
    assert expected_filename in curl_log_path.read_text(encoding="utf-8")

    installed_binary = home_path / ".strix/bin/strix"
    installed_result = subprocess.run(  # noqa: S603
        [installed_binary, "--version"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert installed_result.stdout.strip() == f"strix {RELEASE_VERSION}"
