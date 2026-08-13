"""
app.py

Minimal Flask web wrapper around the existing redact.py PII redaction
pipeline, for cloud deployment (Render/Railway/etc). Does not change any
detection logic -- it just gives the CLI tool a web interface:

  GET  /            -> simple upload form
  POST /redact       -> accepts an uploaded .docx, runs redact_document(),
                         returns the redacted .docx as a file download
"""

import os
import tempfile
import uuid

from flask import Flask, request, send_file, render_template_string, abort

from redact import redact_document

app = Flask(__name__)

UPLOAD_FORM = """
<!doctype html>
<html>
<head><title>PII Redaction Tool</title></head>
<body style="font-family: sans-serif; max-width: 600px; margin: 60px auto;">
  <h2>PII Redaction Tool</h2>
  <p>Upload a .docx file. Detected PII (names, companies, emails, phones,
     addresses, SSNs, credit cards, IPs, dates of birth) will be replaced
     with consistent fake values, and you'll get the redacted .docx back.</p>
  <form action="/redact" method="post" enctype="multipart/form-data">
    <input type="file" name="file" accept=".docx" required>
    <br><br>
    <button type="submit">Redact</button>
  </form>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(UPLOAD_FORM)


@app.route("/redact", methods=["POST"])
def redact():
    if "file" not in request.files:
        abort(400, "No file uploaded.")

    uploaded = request.files["file"]
    if not uploaded.filename.lower().endswith(".docx"):
        abort(400, "Please upload a .docx file.")

    # Use a unique subfolder per request so concurrent uploads never collide
    work_dir = tempfile.mkdtemp(prefix="pii_redact_")
    input_path = os.path.join(work_dir, "input.docx")
    output_path = os.path.join(work_dir, "redacted_output.docx")
    audit_path = os.path.join(work_dir, "audit_log.csv")

    uploaded.save(input_path)

    redact_document(input_path, output_path, audit_path)

    download_name = f"redacted_{uploaded.filename}"
    return send_file(
        output_path,
        as_attachment=True,
        download_name=download_name,
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
