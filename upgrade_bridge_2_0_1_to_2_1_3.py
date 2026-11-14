#!/usr/bin/env python3
"""Safely bridge Global Home 2.0.1 to the published 2.1.3 management code.

This intentionally does not run install.sh, start/stop services, or read/write
Global Home node state. It validates the release and atomically replaces only
the package files under /opt/global-home-nodes.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile
import zlib


APP_DIR = Path("/opt/global-home-nodes")
GL_LINK = Path("/usr/local/bin/gl")
BACKUP_ROOT = Path("/root/global-home-nodes-code-backups")
RAW_BASE = "https://raw.githubusercontent.com/Berry-Blog/global/main/"
MANIFEST_URL = RAW_BASE + "update/manifest.json"
CURRENT_VERSION = "2.0.1"
TARGET_VERSION = "2.1.3"
TARGET_ADAPTER_VERSION = "1.0.0"
ARCHIVE_PATH = "global-home-nodes-v2.1.3.zip"
ARCHIVE_SHA256 = "73b669801565fb93a24dee0311fcc81a3226d48ece16fa807fb0e6d8f1f005b1"
MAX_MANIFEST = 32 * 1024
MAX_ARCHIVE = 16 * 1024 * 1024
MAX_MEMBER = 4 * 1024 * 1024
MAX_TOTAL_UNCOMPRESSED = 16 * 1024 * 1024

PACKAGE_FILES = frozenset(
    {
        "VERSION.json",
        "core.py",
        "deploy.py",
        "relay_export.py",
        "lazycat_adapter.py",
        "update_manager.py",
        "extract.exp",
        "gl",
        "install.sh",
        "README.md",
        "LICENSE",
        "release.json",
        "SHA256SUMS",
    }
)
RELEASE_FILES = frozenset(PACKAGE_FILES - {"release.json", "SHA256SUMS"})
CHECKSUM_FILES = frozenset(PACKAGE_FILES - {"SHA256SUMS"})
MANIFEST_KEYS = frozenset(
    {"schema", "tool", "version", "adapter_version", "archive_path", "archive_sha256"}
)


class UpgradeError(RuntimeError):
    """An expected validation or transaction failure."""


def _json_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON key")
        value[key] = item
    return value


def _decode_json(raw: bytes, label: str):
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_json_object)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        raise UpgradeError(f"{label}不是有效且无重复键的UTF-8 JSON") from None
    if not isinstance(value, dict):
        raise UpgradeError(f"{label}顶层必须是JSON对象")
    return value


def _read_https(url: str, maximum: int) -> bytes:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "raw.githubusercontent.com" or parsed.username or parsed.password:
        raise UpgradeError("下载地址不是受信任的 GitHub HTTPS 地址")
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Global-Home-Upgrade-Bridge/2.0.1-to-2.1.3", "Accept": "application/json, application/zip, */*"},
    )
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            final = urllib.parse.urlparse(response.geturl())
            if final.scheme != "https" or final.hostname != "raw.githubusercontent.com":
                raise UpgradeError("GitHub 下载跳转到非预期站点，已停止")
            length = response.headers.get("Content-Length")
            if length and int(length) > maximum:
                raise UpgradeError("下载文件超过大小限制")
            body = response.read(maximum + 1)
    except UpgradeError:
        raise
    except (OSError, ValueError, urllib.error.URLError):
        raise UpgradeError("无法通过经过证书验证的 HTTPS 从 GitHub 获取升级文件") from None
    if len(body) > maximum:
        raise UpgradeError("下载文件超过大小限制")
    return body


def validate_manifest(raw: bytes) -> dict:
    if not isinstance(raw, bytes) or len(raw) > MAX_MANIFEST:
        raise UpgradeError("更新清单缺失或超过大小限制")
    release = _decode_json(raw, "GitHub 更新清单")
    if set(release) != MANIFEST_KEYS:
        raise UpgradeError("更新清单字段不符合固定格式")
    if type(release.get("schema")) is not int or release["schema"] != 1:
        raise UpgradeError("更新清单 schema 不受支持")
    if release.get("tool") != "global-home-nodes":
        raise UpgradeError("更新清单不是 Global Home 发布包")
    if release.get("version") != TARGET_VERSION or release.get("adapter_version") != TARGET_ADAPTER_VERSION:
        raise UpgradeError("更新清单版本不是本桥接器允许的 2.1.3 / 1.0.0")
    archive_path = release.get("archive_path")
    if archive_path != ARCHIVE_PATH:
        raise UpgradeError("更新清单源码路径与固定发布包不一致")
    if release.get("archive_sha256") != ARCHIVE_SHA256:
        raise UpgradeError("更新清单源码 ZIP SHA256 与桥接器固定值不一致")
    return release


def _safe_archive_member(info: zipfile.ZipInfo) -> str:
    name = info.filename
    path = PurePosixPath(name)
    mode = (info.external_attr >> 16) & 0xFFFF
    file_type = stat.S_IFMT(mode)
    if (
        "\\" in name
        or path.is_absolute()
        or any(part in ("", ".", "..") for part in path.parts)
        or len(path.parts) != 2
        or path.parts[0] != "global-home-nodes"
        or path.parts[1] not in PACKAGE_FILES
        or info.is_dir()
    ):
        raise UpgradeError("源码 ZIP 包含未知或不安全路径")
    if file_type not in (0, stat.S_IFREG) or stat.S_ISLNK(mode) or info.flag_bits & 1:
        raise UpgradeError("源码 ZIP 包含链接、非普通文件或加密条目")
    if info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
        raise UpgradeError("源码 ZIP 使用了不支持的压缩格式")
    if info.file_size < 0 or info.file_size > MAX_MEMBER:
        raise UpgradeError("源码 ZIP 单文件超过大小限制")
    return path.parts[1]


def _validate_inner_metadata(files: dict[str, bytes], release: dict) -> None:
    release_meta = _decode_json(files["release.json"], "源码包 release.json")
    version_doc = _decode_json(files["VERSION.json"], "源码包 VERSION.json")
    if set(release_meta) != {"tool", "version", "adapter_version", "files"}:
        raise UpgradeError("源码包 release.json 字段不符合固定格式")
    if (
        release_meta.get("tool") != "global-home-nodes"
        or release_meta.get("version") != release["version"]
        or release_meta.get("adapter_version") != release["adapter_version"]
        or set(version_doc) != {"version", "adapter_version"}
        or version_doc != {"version": release["version"], "adapter_version": release["adapter_version"]}
    ):
        raise UpgradeError("源码包版本元数据与 GitHub 更新清单不一致")
    metadata_files = release_meta.get("files")
    if (
        not isinstance(metadata_files, list)
        or len(metadata_files) != len(RELEASE_FILES)
        or any(not isinstance(name, str) for name in metadata_files)
        or set(metadata_files) != RELEASE_FILES
    ):
        raise UpgradeError("源码包 release.json 文件清单不完整或含未知文件")

    try:
        checksums = files["SHA256SUMS"].decode("utf-8", errors="strict").splitlines()
    except UnicodeDecodeError:
        raise UpgradeError("源码包 SHA256SUMS 不是有效 UTF-8") from None
    good = set()
    for line in checksums:
        match = re.fullmatch(r"([0-9a-f]{64})  ([A-Za-z0-9._-]+)", line)
        if not match:
            raise UpgradeError("源码包 SHA256SUMS 格式无效")
        digest, name = match.groups()
        if name not in CHECKSUM_FILES or name in good or name not in files:
            raise UpgradeError("源码包 SHA256SUMS 包含未知或重复文件")
        if hashlib.sha256(files[name]).hexdigest() != digest:
            raise UpgradeError("源码包内部 SHA256 校验失败：" + name)
        good.add(name)
    if good != CHECKSUM_FILES:
        raise UpgradeError("源码包 SHA256SUMS 未逐项覆盖完整文件清单")


def validate_archive(raw: bytes, release: dict) -> dict[str, bytes]:
    if not isinstance(raw, bytes) or len(raw) > MAX_ARCHIVE:
        raise UpgradeError("源码 ZIP 缺失或超过大小限制")
    if hashlib.sha256(raw).hexdigest() != release.get("archive_sha256"):
        raise UpgradeError("源码 ZIP SHA256 不匹配，未写入文件")
    expected = {"global-home-nodes/" + name for name in PACKAGE_FILES}
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            infos = archive.infolist()
            if len(infos) != len(expected):
                raise UpgradeError("源码 ZIP 条目数与 13 个固定文件不一致")
            names = []
            files = {}
            total = 0
            for info in infos:
                name = _safe_archive_member(info)
                names.append(info.filename)
                total += info.file_size
                if total > MAX_TOTAL_UNCOMPRESSED:
                    raise UpgradeError("源码 ZIP 解压后总大小超过限制")
                content = archive.read(info)  # Reading every member also verifies its CRC.
                if len(content) != info.file_size:
                    raise UpgradeError("源码 ZIP 文件长度与目录记录不一致")
                files[name] = content
            if len(names) != len(set(names)) or set(names) != expected or set(files) != PACKAGE_FILES:
                raise UpgradeError("源码 ZIP 文件清单不符合固定的 13 项清单")
    except UpgradeError:
        raise
    except (zipfile.BadZipFile, OSError, RuntimeError, NotImplementedError, EOFError, zlib.error):
        raise UpgradeError("源码 ZIP 损坏或无法安全读取") from None

    _validate_inner_metadata(files, release)
    return files


def _installed_version(app_dir: Path) -> str:
    app_dir = Path(app_dir)
    if app_dir.is_symlink() or not app_dir.is_dir():
        raise UpgradeError("程序目录不存在或不是普通目录，拒绝桥接")
    marker = app_dir / "INSTALLER-MARKER"
    version_path = app_dir / "VERSION.json"
    if marker.is_symlink() or version_path.is_symlink():
        raise UpgradeError("安装标记或版本文件是符号链接，拒绝桥接")
    try:
        marker_value = marker.read_text(encoding="utf-8").strip()
        version_doc = _decode_json(version_path.read_bytes(), "本地 VERSION.json")
    except OSError:
        raise UpgradeError("找不到 Global Home 安装标记或版本文件") from None
    if marker_value != "global-home-nodes-v2":
        raise UpgradeError("安装标记不是 Global Home v2，拒绝桥接")
    version = version_doc.get("version")
    if (
        set(version_doc) != {"version", "adapter_version"}
        or version != CURRENT_VERSION
        or version_doc.get("adapter_version") != TARGET_ADAPTER_VERSION
    ):
        raise UpgradeError(f"此桥接器只适用于 Global Home 2.0.1（当前为 {version!r}）")
    return version


def _check_gl_link(app_dir: Path, gl_link: Path) -> bool:
    app_dir, gl_link = Path(app_dir), Path(gl_link)
    if gl_link.parent.is_symlink() or not gl_link.parent.is_dir():
        raise UpgradeError("gl 命令目录不是普通目录，拒绝修改")
    if gl_link.is_symlink():
        if os.readlink(gl_link) != str(app_dir / "gl"):
            raise UpgradeError("gl 命令已指向其他目标，拒绝覆盖")
        return True
    if gl_link.exists():
        raise UpgradeError("gl 命令已被其他文件占用，拒绝覆盖")
    return False


def _smoke_test(directory: Path) -> None:
    directory = Path(directory)
    gl = directory / "gl"
    if not gl.is_file() or not os.access(gl, os.X_OK):
        raise UpgradeError("升级包缺少可执行的 gl 命令")
    if gl.read_bytes().splitlines()[:1] != [b"#!/bin/sh"]:
        raise UpgradeError("gl 命令文件格式无效")
    code = (
        "import sys; sys.path.insert(0, sys.argv[1]); "
        "import core, deploy, lazycat_adapter, update_manager, relay_export"
    )
    try:
        result = subprocess.run(
            [sys.executable, "-c", code, str(directory)],
            cwd=str(directory),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise UpgradeError("管理模块导入检查无法完成") from None
    if result.returncode != 0:
        raise UpgradeError("管理模块导入检查失败")


def _file_mode(name: str) -> int:
    return 0o700 if name == "gl" or name.endswith((".py", ".exp")) else 0o600


def _create_gl_link(app_dir: Path, gl_link: Path) -> None:
    if gl_link.is_symlink() and os.readlink(gl_link) == str(app_dir / "gl"):
        return
    # symlink() creates the link exclusively and refuses to replace a path
    # that appeared after the preflight check.
    os.symlink(str(app_dir / "gl"), gl_link)


def install_verified_files(
    files: dict[str, bytes],
    app_dir: Path = APP_DIR,
    gl_link: Path = GL_LINK,
    backup_root: Path = BACKUP_ROOT,
    smoke_test=_smoke_test,
) -> Path:
    app_dir, gl_link, backup_root = Path(app_dir), Path(gl_link), Path(backup_root)
    if set(files) != PACKAGE_FILES or any(not isinstance(data, bytes) for data in files.values()):
        raise UpgradeError("待安装文件清单不是已验证的完整 13 项发布包")
    _installed_version(app_dir)
    gl_existed = _check_gl_link(app_dir, gl_link)
    originals = {}
    for name in PACKAGE_FILES:
        target = app_dir / name
        if target.is_symlink() or (target.exists() and not target.is_file()):
            raise UpgradeError("程序文件不是普通文件，拒绝覆盖：" + name)
        if target.exists():
            originals[name] = (target.read_bytes(), stat.S_IMODE(target.stat().st_mode))
        else:
            originals[name] = None

    try:
        if backup_root.is_symlink() or (backup_root.exists() and not backup_root.is_dir()):
            raise UpgradeError("管理程序备份目录不是普通目录，拒绝继续")
        backup_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        if backup_root.is_symlink() or not backup_root.is_dir():
            raise UpgradeError("管理程序备份目录不是普通目录，拒绝继续")
        os.chmod(backup_root, 0o700)
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = backup_root / (stamp + "-" + os.urandom(3).hex() + "-2.0.1-to-2.1.3")
        backup.mkdir(mode=0o700, exist_ok=False)
        os.chmod(backup, 0o700)
        for name, original in originals.items():
            if original is not None:
                backup_path = backup / name
                backup_path.write_bytes(original[0])
                os.chmod(backup_path, 0o600)
    except (OSError, UpgradeError):
        raise UpgradeError("无法创建安全的管理程序备份；没有替换程序文件") from None

    stage = None
    changed = []
    gl_created = False
    try:
        stage = Path(tempfile.mkdtemp(prefix=".upgrade-bridge-", dir=str(app_dir)))
        os.chmod(stage, 0o700)
        for name in sorted(PACKAGE_FILES):
            stage_file = stage / name
            with stage_file.open("xb") as stream:
                stream.write(files[name])
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(stage_file, _file_mode(name))
        smoke_test(stage)

        for name in sorted(PACKAGE_FILES):
            os.replace(stage / name, app_dir / name)
            changed.append(name)
            os.chmod(app_dir / name, _file_mode(name))
        if not gl_existed:
            _create_gl_link(app_dir, gl_link)
            gl_created = True
        smoke_test(app_dir)
        return backup
    except BaseException as exc:
        if gl_created and gl_link.is_symlink() and os.readlink(gl_link) == str(app_dir / "gl"):
            gl_link.unlink()
        rollback_error = None
        if stage is not None:
            for name in reversed(changed):
                target = app_dir / name
                original = originals[name]
                try:
                    if original is None:
                        target.unlink(missing_ok=True)
                    else:
                        rollback = stage / (name + ".rollback")
                        rollback.write_bytes(original[0])
                        os.chmod(rollback, original[1])
                        os.replace(rollback, target)
                except OSError:
                    rollback_error = name
        if rollback_error:
            raise UpgradeError(f"升级失败；回滚文件 {rollback_error} 也失败，请使用备份目录恢复") from None
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        raise UpgradeError("升级失败，已回滚管理程序文件；节点配置和服务未修改") from None
    finally:
        if stage is not None:
            shutil.rmtree(stage, ignore_errors=True)


def run(check_only: bool = False) -> Path | None:
    _installed_version(APP_DIR)
    gl_existed = _check_gl_link(APP_DIR, GL_LINK)
    release = validate_manifest(_read_https(MANIFEST_URL, MAX_MANIFEST))
    archive_url = urllib.parse.urljoin(RAW_BASE, release["archive_path"])
    files = validate_archive(_read_https(archive_url, MAX_ARCHIVE), release)
    print("GitHub manifest、固定版本、ZIP SHA256、13 项清单、CRC、内部 SHA256 和版本元数据均已验证。")
    if check_only:
        print("检查完成；没有写入文件、触碰节点配置或改变服务。")
        return None
    backup = install_verified_files(files, APP_DIR, GL_LINK, BACKUP_ROOT)
    print("管理程序已从 2.0.1 安全桥接到 2.1.3；现有节点配置、Xray、UUID、Reality 参数和服务未修改。")
    print(f"管理代码备份：{backup}")
    if not gl_existed:
        print(f"已创建 gl 命令链接：{GL_LINK} -> {APP_DIR / 'gl'}")
    print("Dogma relay 导出可运行：gl export-relay")
    return backup


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Global Home 2.0.1 到 2.1.3 安全升级桥接")
    parser.add_argument("--check-only", action="store_true", help="下载并校验发布包，但不写入文件")
    args = parser.parse_args(argv)
    if os.geteuid() != 0:
        print("请用 sudo 运行此桥接器。", file=sys.stderr)
        return 1
    try:
        run(check_only=args.check_only)
    except UpgradeError as exc:
        print(f"升级桥接已停止：{exc}", file=sys.stderr)
        return 1
    except OSError:
        print("升级桥接遇到文件系统错误；请检查权限和磁盘空间。若文件替换已开始，管理程序会回滚并保留备份。", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
