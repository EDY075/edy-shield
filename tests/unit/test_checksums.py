"""Testes unitários para o módulo checksums — criação e verificação."""

from hashlib import md5, sha1, sha256
from pathlib import Path

import pytest

from app.core.checksums.checksum import (
    SUPPORTED_SUFFIXES,
    ChecksumError,
    create_checksum_file,
    parse_checksum_file,
    verify_checksum_file,
)


def _digest_hex(data: bytes, algorithm: str) -> str:
    if algorithm == "SHA256":
        return sha256(data).hexdigest()
    if algorithm == "SHA1":
        return sha1(data).hexdigest()
    if algorithm == "MD5":
        return md5(data).hexdigest()
    raise AssertionError(algorithm)


class TestCreateChecksumFile:
    def test_create_sha256(self, tmp_path: Path) -> None:
        (tmp_path / "a.txt").write_text("aaa")
        (tmp_path / "b.txt").write_text("bbb")
        out = tmp_path / "checksums.sha256"

        count = create_checksum_file(tmp_path, out, algorithm="SHA256")
        assert count == 2
        assert out.exists()
        content = out.read_text(encoding="utf-8")
        assert "a.txt" in content and "b.txt" in content
        # cada linha: digest + 2 espaços + filename
        for line in content.strip().splitlines():
            digest, _, filename = line.partition("  ")
            assert len(digest) == 64
            assert filename in {"a.txt", "b.txt"}

    def test_create_sha1_and_md5(self, tmp_path: Path) -> None:
        (tmp_path / "f.dat").write_bytes(b"data")
        for algo, suffix in [("SHA1", ".sha1"), ("MD5", ".md5")]:
            out = tmp_path / f"checksums{suffix}"
            count = create_checksum_file(tmp_path, out, algorithm=algo)
            assert count == 1
            digest, _, filename = out.read_text(encoding="utf-8").strip().partition("  ")
            assert digest == _digest_hex(b"data", algo)
            assert filename == "f.dat"

    def test_create_recursive(self, tmp_path: Path) -> None:
        (tmp_path / "top.txt").write_text("top")
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "deep.txt").write_text("deep")
        out = tmp_path / "all.sha256"

        create_checksum_file(tmp_path, out, algorithm="SHA256", recursive=True)
        content = out.read_text(encoding="utf-8")
        assert "top.txt" in content
        assert "sub/deep.txt" in content


class TestParseChecksumFile:
    def test_parse_valid(self, tmp_path: Path) -> None:
        f = tmp_path / "c.sha256"
        zeros, ones = "0" * 64, "1" * 64
        f.write_text(f"{zeros}  file1.txt\n{ones} *file2.txt\n", encoding="utf-8")
        entries = parse_checksum_file(f)
        assert entries == ((zeros, "file1.txt"), (ones, "file2.txt"))

    def test_parse_blank_and_comments(self, tmp_path: Path) -> None:
        f = tmp_path / "c.sha256"
        zeros = "0" * 64
        f.write_text(f"# comentário\n\n{zeros}  a.txt\n", encoding="utf-8")
        entries = parse_checksum_file(f)
        assert entries == ((zeros, "a.txt"),)

    def test_parse_rejects_malformed(self, tmp_path: Path) -> None:
        f = tmp_path / "c.sha256"
        f.write_text("onlydigest\n", encoding="utf-8")
        with pytest.raises(ChecksumError):
            parse_checksum_file(f)

    def test_parse_rejects_non_hex(self, tmp_path: Path) -> None:
        f = tmp_path / "c.sha256"
        f.write_text("Z" * 64 + "  a.txt\n", encoding="utf-8")
        with pytest.raises(ChecksumError):
            parse_checksum_file(f)

    def test_parse_rejects_wrong_length(self, tmp_path: Path) -> None:
        f = tmp_path / "c.sha256"
        f.write_text("a" * 48 + "  a.txt\n", encoding="utf-8")
        with pytest.raises(ChecksumError):
            parse_checksum_file(f)


class TestVerifyChecksumFile:
    def test_verify_ok(self, tmp_path: Path) -> None:
        (tmp_path / "a.txt").write_text("hello")
        digest = sha256(b"hello").hexdigest()
        cf = tmp_path / "c.sha256"
        cf.write_text(f"{digest}  a.txt\n", encoding="utf-8")

        report = verify_checksum_file(cf)
        assert report.total == 1
        assert report.ok == 1
        assert report.mismatch == 0
        assert report.missing == 0
        assert report.invalid == 0
        assert report.ok_all

    def test_verify_mismatch(self, tmp_path: Path) -> None:
        (tmp_path / "a.txt").write_text("hello")
        wrong = sha256(b"bye").hexdigest()
        cf = tmp_path / "c.sha256"
        cf.write_text(f"{wrong}  a.txt\n", encoding="utf-8")

        report = verify_checksum_file(cf)
        assert report.total == 1
        assert report.ok == 0
        assert report.mismatch == 1
        assert not report.ok_all
        assert report.entries[0].status == "mismatch"
        assert report.entries[0].actual is not None

    def test_verify_missing_file(self, tmp_path: Path) -> None:
        cf = tmp_path / "c.sha256"
        zeros = "0" * 64
        cf.write_text(f"{zeros}  gone.txt\n", encoding="utf-8")
        report = verify_checksum_file(cf)
        assert report.missing == 1
        assert not report.ok_all

    def test_verify_invalid_line(self, tmp_path: Path) -> None:
        cf = tmp_path / "c.sha256"
        cf.write_text("badline\n", encoding="utf-8")
        report = verify_checksum_file(cf)
        assert report.invalid == 1
        assert not report.ok_all

    def test_verify_comments_ignored(self, tmp_path: Path) -> None:
        (tmp_path / "a.txt").write_text("hello")
        digest = sha256(b"hello").hexdigest()
        cf = tmp_path / "c.sha256"
        cf.write_text(f"# note\n{digest}  a.txt\n", encoding="utf-8")
        report = verify_checksum_file(cf)
        assert report.total == 1
        assert report.ok == 1

    def test_verify_relative_paths(self, tmp_path: Path) -> None:
        sub = tmp_path / "files"
        sub.mkdir()
        (sub / "inner.txt").write_text("inner")
        digest = sha256(b"inner").hexdigest()
        cf = tmp_path / "c.sha256"
        cf.write_text(f"{digest}  files/inner.txt\n", encoding="utf-8")
        report = verify_checksum_file(cf)
        assert report.ok == 1

    def test_verify_path_traversal_rejected(self, tmp_path: Path) -> None:
        outside = tmp_path.parent / "secret.txt"
        outside.write_text("secret")
        cf = tmp_path / "c.sha256"
        zeros = "0" * 64
        cf.write_text(f"{zeros}  ../secret.txt\n", encoding="utf-8")
        report = verify_checksum_file(cf)
        # entrada rejeitada (invalid) — nunca lê fora da raiz
        assert report.invalid == 1
        assert report.ok == 0
        assert report.missing == 0

    def test_verify_sha1_and_md5(self, tmp_path: Path) -> None:
        (tmp_path / "a.txt").write_text("data")
        for algo in ["SHA1", "MD5"]:
            digest = _digest_hex(b"data", algo)
            cf = tmp_path / f"c.{algo.lower()}"
            cf.write_text(f"{digest}  a.txt\n", encoding="utf-8")
            report = verify_checksum_file(cf)
            assert report.ok == 1, algo


class TestSuffixes:
    def test_supported_suffixes(self) -> None:
        assert {
            ".sha256",
            ".sha256sum",
            ".sha1",
            ".md5",
            ".md5sum",
        } == SUPPORTED_SUFFIXES
