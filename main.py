
import subprocess
import sys
import time
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parent
FASTAPI_HOST = "127.0.0.1"
FASTAPI_PORT = 8000
STREAMLIT_PORT = 8501
HEALTH_URL = f"http://{FASTAPI_HOST}:{FASTAPI_PORT}/health"


def start_fastapi():
    print("Starting FastAPI backend...")

    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "api.main:app",
            "--host",
            FASTAPI_HOST,
            "--port",
            str(FASTAPI_PORT),
        ],
        cwd=PROJECT_ROOT,
    )


def wait_for_fastapi(process, timeout=30):
    print("Waiting for FastAPI to become available...")
    start_time = time.time()

    while time.time() - start_time < timeout:
        if process.poll() is not None:
            raise RuntimeError("FastAPI process stopped unexpectedly.")

        try:
            response = requests.get(HEALTH_URL, timeout=1)

            if response.status_code == 200:
                print("FastAPI is ready.")
                return

        except requests.RequestException:
            pass

        time.sleep(0.5)

    raise TimeoutError("FastAPI did not become available within 30 seconds.")


def start_streamlit():
    print("Starting Streamlit frontend...")

    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            "frontend/app.py",
            "--server.port",
            str(STREAMLIT_PORT),
        ],
        cwd=PROJECT_ROOT,
    )


def main():
    fastapi_process = None
    streamlit_process = None

    try:
        fastapi_process = start_fastapi()
        wait_for_fastapi(fastapi_process)
        streamlit_process = start_streamlit()

        print(f"FastAPI: http://{FASTAPI_HOST}:{FASTAPI_PORT}")
        print(f"API Docs: http://{FASTAPI_HOST}:{FASTAPI_PORT}/docs")
        print(f"Streamlit: http://localhost:{STREAMLIT_PORT}")
        print("Press Ctrl+C to stop the application.")

        while True:
            if fastapi_process.poll() is not None:
                print("FastAPI stopped.")
                break

            if streamlit_process.poll() is not None:
                print("Streamlit stopped.")
                break

            time.sleep(1)

    except KeyboardInterrupt:
        print("\nShutting down...")

    except Exception as exc:
        print(f"\nApplication failed: {exc}")

    finally:
        if streamlit_process is not None:
            print("Stopping Streamlit...")
            streamlit_process.terminate()

            try:
                streamlit_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                streamlit_process.kill()

        if fastapi_process is not None:
            print("Stopping FastAPI...")
            fastapi_process.terminate()

            try:
                fastapi_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                fastapi_process.kill()

        print("Application stopped.")


if __name__ == "__main__":
    main()