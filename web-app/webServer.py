import http.server
import socketserver

PORT = 5001

# Define the handler to serve files from the current directory
Handler = http.server.SimpleHTTPRequestHandler

# Create an HTTP server instance
with socketserver.TCPServer(("", PORT), Handler) as httpd:
    print(f"Serving on port {PORT}")
    # Start the server
    httpd.serve_forever()