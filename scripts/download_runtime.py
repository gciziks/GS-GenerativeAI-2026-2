"""Download public, version-pinned artifacts; validate LFS/GitHub hashes."""
from pathlib import Path
import hashlib
import json
import urllib.request
import zipfile
import zlib
from ranged_download import transfer

ROOT = Path(__file__).resolve().parents[1]
REVISION = "a06e946bb6b655725eafa393f4a9745d460374c9"
REPO = "unsloth/Qwen3-4B-Instruct-2507-GGUF"
FILE = "Qwen3-4B-Instruct-2507-Q4_K_M.gguf"
TAG = "b12287"


def download(url, path, expected=None, size=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        print(f"Downloading {path.name}", flush=True)
        part = path.with_suffix(path.suffix + ".part")
        if size or 'huggingface.co' in url:
            if size is None:
                response = urllib.request.urlopen(urllib.request.Request(url, method='HEAD'), timeout=30)
                size = int(response.headers['Content-Length'])
            transfer(url, path, size)
        else:
            urllib.request.urlretrieve(url, part)
            part.replace(path)
    digest = hashlib.file_digest(path.open("rb"), "sha256").hexdigest()
    if expected and digest != expected.removeprefix("sha256:"):
        raise ValueError(f"Hash mismatch: {path}")
    return digest


def main():
    release = json.load(urllib.request.urlopen(f"https://api.github.com/repos/ggml-org/llama.cpp/releases/tags/{TAG}"))
    records = []
    for asset in release["assets"]:
        if asset["name"] in {f"llama-{TAG}-bin-win-cuda-12.4-x64.zip", "cudart-llama-bin-win-cuda-12.4-x64.zip"}:
            path = ROOT / ".runtime" / asset["name"]
            digest = download(asset["browser_download_url"], path, asset.get("digest"), asset["size"])
            target = ROOT / ".runtime" / "llama"
            target.mkdir(exist_ok=True)
            with zipfile.ZipFile(path) as archive:
                for name in archive.namelist():
                    if not (target / name).resolve().is_relative_to(target.resolve()):
                        raise ValueError("Invalid zip path")
                for member in archive.infolist():
                    output = target / member.filename
                    if (not output.exists() or output.stat().st_size != member.file_size
                            or zlib.crc32(output.read_bytes()) != member.CRC):
                        archive.extract(member, target)
            records.append({"url": asset["browser_download_url"], "sha256": digest, "tag": TAG})
    tree = json.load(urllib.request.urlopen(f"https://huggingface.co/api/models/{REPO}/tree/{REVISION}"))
    entry = next(f for f in tree if f["path"] == FILE)
    url = f"https://huggingface.co/{REPO}/resolve/{REVISION}/{FILE}"
    digest = download(url, ROOT / "models" / FILE, entry["lfs"]["oid"])
    records.append({"url": url, "sha256": digest, "repository": REPO, "revision": REVISION,
                    "upstream": "Qwen/Qwen3-4B-Instruct-2507", "license": "Apache-2.0", "quantization": "Q4_K_M"})
    config = ROOT / "docs" / "evidencias" / "runtime-downloads.json"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(json.dumps(records, indent=2), encoding="utf-8")
    print("Verified runtime artifacts", flush=True)


if __name__ == "__main__":
    main()
