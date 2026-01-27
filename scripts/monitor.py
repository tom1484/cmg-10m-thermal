from typing import Generator, Optional

import typer

import subprocess
import time
import json
import select
import atexit

from collections import deque
import numpy as np


READ_COMMAND = [
    "thermo-cli",
    "fuse",
    "-C",
    "thermo_config.yaml",
    "--",
    "--power",
    "-s",
    "1",
]
TERMINATE_COMMAND = ["cmg-cli", "set", "--idle"]
WHEEL_ON_COMMAND = ["cmg-cli", "set", "--wheel"]

KEYS_TO_CHECK_THRESHOLD = [
    "POWER_TMP2",
    "POWER_TMP3",
    "THERMO_X_TEMP",
    "THERMO_Z_TEMP",
    "THERMO_SP_TEMP",
    "THERMO_NSP_TEMP",
]
KEYS_TO_CHECK_STEADY = [
    "THERMO_X_TEMP",
    "THERMO_Z_TEMP",
    "THERMO_SP_TEMP",
    "THERMO_NSP_TEMP",
]


class Logger:
    def __init__(self, log_path: str, log_append: bool = False):
        self.log_file = open(log_path, "a" if log_append else "w")
        self.log_append = log_append
    
    def log_columns(self, columns: dict):
        if not self.log_append:
            self.log_file.write(",".join(columns.keys()) + "\n")
    
    def log_row(self, row: dict):
        self.log_file.write(",".join(str(row[col]) for col in row.keys()) + "\n")
        self.log_file.flush()

        print(f"Timestamp: {row['TIME']}")
        for key in row.keys():
            if key != "TIME":
                print(f"  {key}: {row[key]}")
        print()


class Reader:
    def __init__(self):
        self.columns = None
        self.lines = 0

    def timestamp_to_seconds(self, ts: str) -> float:
        # Format: YEAR-MONTH-DAYTHOUR:MINUTE:SECOND.MICROSECOND
        date, time = ts.split("T")
        year, month, day = map(int, date.split("-"))
        hour, minute, second = map(float, time.split(":"))
        second, microsecond = map(int, str(second).split("."))
        total_seconds = (
            (((year * 365 + month * 30 + day) * 24 + hour) * 60 + minute) * 60
            + second
            + microsecond / 1_000_000
        )
        return total_seconds

    def parse(self, line: str) -> dict:
        data = json.loads(line)

        row = {}
        row["TIME"] = self.timestamp_to_seconds(data["TIMESTAMP"])

        power = data["POWER"]
        for key, value in power.items():
            row[f"POWER_{key}"] = value

        thermo = data["THERMOCOUPLE"]
        for pos, data in thermo.items():
            for key, value in data.items():
                row[f"THERMO_{pos}_{key}"] = value

        return row
        
    def read(self) -> Generator[tuple[int, dict], None, None]:
        proc = subprocess.Popen(
            READ_COMMAND, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )

        if select.select([proc.stderr], [], [], 0)[0]:
            err_msgs = []
            for line in proc.stderr:
                err_msgs.append(line.strip())
            raise RuntimeError("Failed to start thermo-cli: \n" + "\n".join(err_msgs))

        for line in proc.stdout:
            row = self.parse(line)
            yield self.lines, row
            self.lines += 1


class Device:
    def __init__(
        self,
        threshold: float,
        steady_window: Optional[int] = None,
        steady_threshold: Optional[float] = None,
        steady_check_every: Optional[int] = None,
    ):
        self.terminated = False
        atexit.register(self.terminate)

        self.threshold = threshold

        self.steady_window = steady_window
        self.steady_threshold = steady_threshold
        self.steady_check_every = steady_check_every

        self.steady_history = {key: deque() for key in KEYS_TO_CHECK_STEADY}
        self.last_steady_check = {key: None for key in KEYS_TO_CHECK_STEADY}

    def wheel_on(self, speed: float, gimbal: float = 45):
        print(
            f"Turning on the wheel with speed {speed} Hz and gimbal angle {gimbal} degrees..."
        )
        command = WHEEL_ON_COMMAND + [f"{speed},{gimbal}"]
        subprocess.run(command, check=True)

    def under_threshold(self, row: dict) -> bool:
        for key in KEYS_TO_CHECK_THRESHOLD:
            if row.get(key, 0) >= self.threshold:
                return False
        return True

    def check_steady(self, row: dict) -> bool:
        if (
            self.steady_window is None
            or self.steady_threshold is None
            or self.steady_check_every is None
        ):
            return False
        
        # Skip checking steady state during defer period
        time = row["TIME"]
        steady = {key: False for key in KEYS_TO_CHECK_STEADY}

        for key in KEYS_TO_CHECK_STEADY:
            history = self.steady_history[key]
            temp = row[key]
            time = row["TIME"]

            history.append((time, temp))  # (time, value)
            
            last_entry = history[-1]
            if (
                (self.last_steady_check[key] is not None and time - self.last_steady_check[key] < self.steady_check_every) or
                last_entry[0] - history[0][0] < self.steady_check_every
            ):
                continue
            
            data = [t for _, t in history]
            std = np.std(data)
            print(f"Steady check for {key}: std = {std:.4f} °C over last {last_entry[0] - history[0][0]:.2f} seconds")
            if std < self.steady_threshold:
                steady[key] = True

            self.last_steady_check[key] = time
            while last_entry[0] - history[0][0] >= self.steady_window:
                history.popleft()

        return all(steady.values())

    def terminate(self):
        while not self.terminated:
            print("Terminating device...")
            term_proc = subprocess.Popen(
                TERMINATE_COMMAND,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            _, _ = term_proc.communicate()
            if term_proc.returncode == 0:
                self.terminated = True

        if self.terminated:
            print("Device terminated.")


def main(
    output: str = typer.Argument(..., help="Output CSV file path"),
    append: bool = typer.Option(
        False, help="Append to the output file if it exists"
    ),
    speed: Optional[float] = typer.Option(
        None, help="Wheel speed to turn on the device (Hz)"
    ),
    gimbal: Optional[float] = typer.Option(
        None, help="Gimbal angle to set when turning on the wheel (degrees)"
    ),
    threshold: float = typer.Option(
        70.0, help="Temperature threshold to stop the test (°C)"
    ),
    time_limit: int = typer.Option(
        3600, help="Time limit for the steady test in seconds"
    ),
    defer_start: Optional[int] = typer.Option(
        None, help="Defer motor activation and steady state checking for this many seconds after start (included in time limit)"
    ),
    steady_window: Optional[int] = typer.Option(
        None, help="Time window to check for steadiness in seconds"
    ),
    steady_threshold: Optional[float] = typer.Option(
        None, help="Maximum allowed variation in temperature for steadiness (°C)"
    ),
    steady_check_every: Optional[int] = typer.Option(
        None, help="Interval to check for steadiness in seconds"
    ),
):
    reader = Reader()
    logger = Logger(log_path=output, log_append=append)

    device = Device(
        threshold=threshold,
        steady_window=steady_window,
        steady_threshold=steady_threshold,
        steady_check_every=steady_check_every,
    )

    print("Starting monitoring...")
    if threshold is not None:
        print(f"  Temperature threshold set to {threshold} °C")
    if time_limit is not None:
        print(f"  Time limit set to {time_limit / 3600:.2f} hours")
    if defer_start is not None:
        print(f"  Deferring motor activation and steady state checking for {defer_start / 3600:.2f} hours")
    if speed is not None and gimbal is not None:
        print(f"  Wheel speed set to {speed} Hz with gimbal angle {gimbal} degrees")
    if steady_window is not None and steady_threshold is not None:
        print(
            f"  Steady state checking enabled:"
            + f"    window = {steady_window} seconds, "
            + f"    threshold = {steady_threshold} °C, "
            + f"    check every {steady_check_every} seconds"
        )
    print()

    try:
        start_time = time.time()
        motor_activated = False

        for i, row in reader.read():
            if i == 0:
                logger.log_columns(row)
            logger.log_row(row)
            
            if not device.under_threshold(row):
                print(
                    f"Threshold of {threshold} °C exceeded.\n"
                    + "Stopping the test."
                )
                break
                
            current_time = time.time()
            elapsed_time = current_time - start_time
            if elapsed_time >= time_limit:
                print(
                    f"Time limit of {time_limit} seconds reached.\n"
                    + "Stopping the test."
                )
                break
            
            if defer_start is not None and elapsed_time < defer_start:
                continue
            
            if not motor_activated:
                if speed is not None or gimbal is not None:
                    assert (
                        speed is not None and gimbal is not None
                    ), "Both speed and gimbal must be provided."
                    print("Activating motor...\n")
                    device.wheel_on(speed=speed, gimbal=gimbal)
                motor_activated = True

            if device.check_steady(row):
                print(
                    f"Steady state achieved within {steady_window} seconds "
                    + f"with variation less than {steady_threshold} °C.\n"
                    + "Stopping the test."
                )
                break

    except Exception as e:
        print(e)
    
    device.terminate()


if __name__ == "__main__":
    typer.run(main)
