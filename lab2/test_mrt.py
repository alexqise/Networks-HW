"""
Test script for the MRT protocol.
Runs server, network simulator, and client in subprocesses
and checks the result.
"""

import subprocess
import sys
import time
import os

PYTHON = sys.executable
LAB_DIR = os.path.dirname(os.path.abspath(__file__))

SERVER_PORT = 60000
CLIENT_PORT = 50000
NETWORK_PORT = 51000
SEGMENT_SIZE = 1460
BUFFER_SIZE = 4096


def write_loss_file(loss_rate, bit_error):
    """Write a Loss.txt with the given parameters."""
    path = os.path.join(LAB_DIR, "Loss.txt")
    with open(path, "w") as f:
        f.write(f"0 {loss_rate} {bit_error}\n")


def run_test(name, loss_rate, bit_error, timeout=30):
    """Run a single test case and return pass/fail."""
    print(f"\n{'='*50}")
    print(f"TEST: {name}")
    print(f"  loss_rate={loss_rate}, bit_error={bit_error}")
    print(f"{'='*50}")

    write_loss_file(loss_rate, bit_error)

    # clean up old log files
    for f in [f"log_{SERVER_PORT}.txt", f"log_{CLIENT_PORT}.txt"]:
        path = os.path.join(LAB_DIR, f)
        if os.path.exists(path):
            os.remove(path)

    # start server
    server = subprocess.Popen(
        [PYTHON, "app_server.py", str(SERVER_PORT), str(BUFFER_SIZE)],
        cwd=LAB_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    time.sleep(0.3)

    # start network simulator
    network = subprocess.Popen(
        [PYTHON, "network.py",
         str(NETWORK_PORT), "127.0.0.1", str(CLIENT_PORT),
         "127.0.0.1", str(SERVER_PORT), "Loss.txt"],
        cwd=LAB_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    time.sleep(0.3)

    # start client
    client = subprocess.Popen(
        [PYTHON, "app_client.py",
         str(CLIENT_PORT), "127.0.0.1", str(NETWORK_PORT),
         str(SEGMENT_SIZE)],
        cwd=LAB_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    # wait for client to finish
    try:
        client_stdout, client_stderr = client.communicate(timeout=timeout)
        client_out = client_stdout.decode().strip()
        client_err = client_stderr.decode().strip()
    except subprocess.TimeoutExpired:
        client.kill()
        client_out = ""
        client_err = "TIMEOUT"

    # wait for server to finish
    try:
        server_stdout, server_stderr = server.communicate(timeout=5)
        server_out = server_stdout.decode().strip()
        server_err = server_stderr.decode().strip()
    except subprocess.TimeoutExpired:
        server.kill()
        server_out = ""
        server_err = "TIMEOUT"

    # kill network sim
    network.kill()
    network.wait()

    # print results
    print(f"  Client: {client_out}")
    if client_err:
        print(f"  Client stderr: {client_err}")
    print(f"  Server: {server_out}")
    if server_err:
        print(f"  Server stderr: {server_err}")

    # check log files exist
    client_log = os.path.join(LAB_DIR, f"log_{CLIENT_PORT}.txt")
    server_log = os.path.join(LAB_DIR, f"log_{SERVER_PORT}.txt")
    has_client_log = os.path.exists(client_log)
    has_server_log = os.path.exists(server_log)
    print(f"  Client log exists: {has_client_log}")
    print(f"  Server log exists: {has_server_log}")

    passed = "received 8000 bytes successfully" in server_out
    if passed:
        print(f"  RESULT: PASS")
    else:
        print(f"  RESULT: FAIL")

    return passed


if __name__ == "__main__":
    results = []

    # test 1: no loss
    results.append(("No loss", run_test("No loss", 0.0, 0.0)))

    # test 2: 10% packet loss, no bit errors
    results.append(("10% loss", run_test("10% packet loss", 0.1, 0.0)))

    # test 3: no packet loss, low bit errors
    results.append(("Bit errors", run_test("Bit errors only", 0.0, 0.001)))

    # test 4: 10% loss + bit errors
    results.append(("Loss + errors", run_test("10% loss + bit errors", 0.1, 0.001)))

    # test 5: 30% packet loss
    results.append(("30% loss", run_test("30% packet loss", 0.3, 0.0, timeout=60)))

    # summary
    print(f"\n{'='*50}")
    print("SUMMARY")
    print(f"{'='*50}")
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  {name}: {status}")
    print(f"\n  {sum(p for _, p in results)}/{len(results)} tests passed")
