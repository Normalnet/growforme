import http.server
import socketserver
import os
import sys
from pathlib import Path

PORT = 8000
FRONTEND_DIR = str(Path(__file__).parent / "frontend")

class FixedDirectoryHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=FRONTEND_DIR, **kwargs)

    def translate_path(self, path):
        # Default behavior: translate the URL path to a local file system path 
        # relative to self.directory (which is frontend).
        translated = super().translate_path(path)
        
        # If the requested path is a directory on disk, try appending 'index.html'
        if os.path.isdir(translated):
            index = os.path.join(translated, "index.html")
            if os.path.exists(index):
                return index
                
        return translated

if __name__ == '__main__':
    print(f'Starting frontend server at http://localhost:{PORT}')
    print(f'Serving files from: {FRONTEND_DIR}')
    try:
        # allow_reuse_address prevents "Address already in use" errors during dev restarts
        socketserver.TCPServer.allow_reuse_address = True
        with socketserver.TCPServer(('', PORT), FixedDirectoryHandler) as httpd:
            print("Server is live.")
            httpd.serve_forever()
    except Exception as e:
        print(f"Error starting server: {e}")
