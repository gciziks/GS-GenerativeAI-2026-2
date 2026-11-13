"""Bounded, resumable HTTP range transfer. Final SHA verification is caller responsibility."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import time
import urllib.request


def transfer(url, path, size, block_size=8 * 1024 * 1024):
    path = Path(path)
    parts = path.parent / (path.name + ".parts")
    parts.mkdir(parents=True, exist_ok=True)
    def part(index):
        start = index * block_size
        end = min(size, start + block_size) - 1
        target = parts / str(index)
        if target.exists() and target.stat().st_size == end - start + 1:
            return index
        for attempt in range(5):
            try:
                req = urllib.request.Request(url + ('&' if '?' in url else '?') + f'download=true&part={index}',
                                             headers={'Range': f'bytes={start}-{end}'})
                with urllib.request.urlopen(req, timeout=45) as response:
                    if response.status != 206 or response.headers.get('Content-Range', '').split('/')[0] != f'bytes {start}-{end}':
                        raise ValueError('Server did not honor byte range')
                    data = response.read()
                if len(data) != end - start + 1:
                    raise ValueError('Incomplete byte range')
                target.write_bytes(data)
                return index
            except Exception:
                if attempt == 4:
                    raise
                time.sleep(attempt + 1)
    count = (size + block_size - 1) // block_size
    with ThreadPoolExecutor(max_workers=8) as pool:
        for completed, future in enumerate(as_completed([pool.submit(part, n) for n in range(count)]), 1):
            future.result()
            if completed % 20 == 0 or completed == count:
                print(f'{path.name}: {completed}/{count} blocks', flush=True)
    temporary = path.with_suffix(path.suffix + '.part')
    with temporary.open('wb') as output:
        for index in range(count):
            output.write((parts / str(index)).read_bytes())
    temporary.replace(path)
