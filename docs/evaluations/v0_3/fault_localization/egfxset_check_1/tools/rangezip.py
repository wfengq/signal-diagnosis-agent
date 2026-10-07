"""Read members of a remote zip via HTTP range requests (no full download)."""
import io, sys, time, urllib.request, zipfile

class HttpFile(io.RawIOBase):
    def __init__(self, url):
        self.url = url; self.pos = 0
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req) as r:
            self.size = int(r.headers["Content-Length"])
    def seekable(self): return True
    def readable(self): return True
    def tell(self): return self.pos
    def seek(self, off, whence=0):
        self.pos = off if whence == 0 else self.pos + off if whence == 1 else self.size + off
        return self.pos
    def readinto(self, b):
        n = len(b)
        if n == 0 or self.pos >= self.size: return 0
        end = min(self.pos + n, self.size) - 1
        req = urllib.request.Request(self.url, headers={"Range": f"bytes={self.pos}-{end}"})
        for attempt in range(5):
            try:
                with urllib.request.urlopen(req, timeout=60) as r:
                    data = r.read()
                break
            except OSError:
                if attempt == 4:
                    raise
                time.sleep(2 ** (attempt + 1))
        b[: len(data)] = data; self.pos += len(data)
        return len(data)

def open_zip(name):
    url = f"https://zenodo.org/records/7044411/files/{name}?download=1"
    return zipfile.ZipFile(io.BufferedReader(HttpFile(url), buffer_size=1 << 16))

if __name__ == "__main__":
    z = open_zip(sys.argv[1])
    names = z.namelist()
    print(len(names)); print("\n".join(names[:12]))
