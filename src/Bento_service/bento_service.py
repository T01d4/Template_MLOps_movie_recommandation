import bentoml
from bentoml.io import JSON
import subprocess
import logging
import threading
import os
import signal
import time

svc = bentoml.Service("hybrid_deep_model_service")


LAST_REQUEST_FILE = "/tmp/bento_last_request.txt"
AUTO_SHUTDOWN_MINUTES = 60  # Minuten Inaktivität bis Shutdown

def touch_last_request():
    with open(LAST_REQUEST_FILE, "w") as f:
        f.write(str(time.time()))

def get_last_request_time():
    try:
        with open(LAST_REQUEST_FILE, "r") as f:
            return float(f.read())
    except Exception:
        return None

def auto_shutdown_watcher():
    while True:
        last = get_last_request_time()
        if last is not None:
            inactive_minutes = (time.time() - last) / 60
            if inactive_minutes > AUTO_SHUTDOWN_MINUTES:
                print(f"[AutoShutdown] Keine Requests seit {inactive_minutes:.1f} min – beende Service.")
                os.kill(os.getpid(), signal.SIGTERM)
        time.sleep(60)  # jede Minute prüfen

# Starte Auto-Shutdown-Thread (am Anfang des Scripts)
t = threading.Thread(target=auto_shutdown_watcher, daemon=True)
t.start()


# Lock für Training
training_lock = threading.Lock()

def run_and_log(command, cwd="/app/src"):
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True
        )
        stdout_lines = result.stdout.splitlines() if result.stdout else []
        stderr_lines = result.stderr.splitlines() if result.stderr else []
        return {
            "stdout": result.stdout,
            "stdout_lines": stdout_lines,
            "stderr": result.stderr,
            "stderr_lines": stderr_lines,
            "returncode": result.returncode,
        }
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        return {
            "stdout": "",
            "stdout_lines": [],
            "stderr": f"{str(e)}\n{tb}",
            "stderr_lines": [str(e)] + tb.splitlines(),
            "returncode": 1
        }

@svc.api(input=JSON(), output=JSON())
def train_deep_hybrid_model(body):
    touch_last_request()
    if not training_lock.acquire(blocking=False):
        return {"status": "busy", "msg": "Training already running, try again later."}
    try:
        n_neighbors = body.get("n_neighbors", 10)
        latent_dim = body.get("latent_dim", 64)
        epochs = body.get("epochs", 30)
        tfidf_features = body.get("tfidf_features", 300)
        cmd = [
            "python", "models/train_hybrid_deep_model.py",
            f"--n_neighbors={n_neighbors}",
            f"--latent_dim={latent_dim}",
            f"--epochs={epochs}",
            f"--tfidf_features={tfidf_features}"
        ]
        log_data = run_and_log(cmd, cwd="/app/src")
        result = {
            "status": "finished",
            "stdout": log_data["stdout"],
            "stdout_lines": log_data["stdout_lines"],
            "stderr": log_data["stderr"],
            "stderr_lines": log_data["stderr_lines"],
            "returncode": log_data["returncode"],
            "params_used": {
                "n_neighbors": n_neighbors,
                "latent_dim": latent_dim,
                "epochs": epochs,
                "tfidf_features": tfidf_features
            }
        }
        return result
    finally:
        training_lock.release()

@svc.api(input=JSON(), output=JSON())
def validate_model(body):
    touch_last_request()
    cmd = [
        "python", "models/validate_model.py",
        f"--test_user_count={body.get('test_user_count', 100)}"
    ]
    log_data = run_and_log(cmd, cwd="/app/src")
    return {
        "status": "finished",
        "stdout": log_data["stdout"],
        "stdout_lines": log_data["stdout_lines"],
        "stderr": log_data["stderr"],
        "stderr_lines": log_data["stderr_lines"],
        "returncode": log_data["returncode"]
    }

@svc.api(input=JSON(), output=JSON())
def predict_best_model(body):
    touch_last_request()
    cmd = ["python", "models/predict_best_model.py"]
    log_data = run_and_log(cmd, cwd="/app/src")
    return {
        "status": "finished",
        "stdout": log_data["stdout"],
        "stdout_lines": log_data["stdout_lines"],
        "stderr": log_data["stderr"],
        "stderr_lines": log_data["stderr_lines"],
        "returncode": log_data["returncode"]
    }