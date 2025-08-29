from flask import Flask, request, jsonify
import subprocess
import tempfile
import os
from minio import Minio
from minio.error import S3Error

app = Flask(__name__)

# MinIO configuration - assuming these are passed as environment variables
MINIO_URL = os.environ.get("MINIO_URL", "minio:9000")
MINIO_ACCESS_KEY = os.environ.get("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.environ.get("MINIO_SECRET_KEY", "minioadmin")

minio_client = Minio(
    MINIO_URL,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=False
)

@app.route('/convert', methods=['POST'])
def convert():
    data = request.get_json()
    if not data or 'bucket_name' not in data or 'object_name' not in data:
        return jsonify({"error": "Missing bucket_name or object_name"}), 400

    bucket_name = data['bucket_name']
    object_name = data['object_name']
    job_id = os.path.splitext(os.path.basename(object_name))[0]

    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            # 1. Download the PPTX from MinIO
            local_pptx_path = os.path.join(temp_dir, os.path.basename(object_name))
            minio_client.fget_object(bucket_name, object_name, local_pptx_path)

            # 2. Convert PPTX to PDF
            subprocess.run(
                ["libreoffice", "--headless", "--convert-to", "pdf", "--outdir", temp_dir, local_pptx_path],
                check=True
            )
            local_pdf_path = os.path.join(temp_dir, f"{os.path.splitext(os.path.basename(object_name))[0]}.pdf")
            if not os.path.exists(local_pdf_path):
                raise Exception("PDF conversion failed.")

            # 3. Convert PDF to images using pdftoppm
            # We need to install poppler-utils for this
            image_output_dir = os.path.join(temp_dir, "images")
            os.makedirs(image_output_dir)
            subprocess.run(
                ["pdftoppm", local_pdf_path, os.path.join(image_output_dir, "slide"), "-png"],
                check=True
            )

            # 4. Upload images to MinIO
            image_paths = []
            output_bucket = "presentations" # Assuming a bucket for processed files
            for filename in sorted(os.listdir(image_output_dir)):
                if filename.endswith(".png"):
                    local_image_path = os.path.join(image_output_dir, filename)
                    # Use a clear naming scheme, e.g., presentations/job_id/images/slide-01.png
                    s3_image_name = f"{job_id}/images/{filename}"
                    minio_client.fput_object(output_bucket, s3_image_name, local_image_path)
                    image_paths.append(f"/{output_bucket}/{s3_image_name}")

            return jsonify({"image_paths": image_paths}), 200

        except S3Error as e:
            return jsonify({"error": f"MinIO error: {e}"}), 500
        except subprocess.CalledProcessError as e:
            return jsonify({"error": f"Conversion command failed: {e}"}), 500
        except Exception as e:
            return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8100)
