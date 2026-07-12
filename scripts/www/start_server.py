import http.server
import socketserver
import webbrowser
import os
import threading

os.chdir(os.path.dirname(os.path.abspath(__file__)))

PORT = 9090

handler = http.server.SimpleHTTPRequestHandler

class QuietHandler(handler):
    def log_message(self, format, *args):
        pass  # Suppress default logging

with socketserver.TCPServer(('', PORT), QuietHandler) as httpd:
    url = f'http://127.0.0.1:{PORT}/index.html'
    print(f'Game running at {url}')
    print('Press Ctrl+C to stop')
    webbrowser.open(url)
    httpd.serve_forever()
