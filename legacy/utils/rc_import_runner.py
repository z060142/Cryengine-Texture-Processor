#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Synchronous runner for CryEngine RC FBX import request JSON files."""

from dataclasses import dataclass
import json
import os
import subprocess


@dataclass
class RCImportResult:
    success: bool
    command: list
    json_path: str
    expected_output_path: str
    returncode: int | None = None
    stdout: str = ""
    stderr: str = ""
    error: str = ""


def load_request_payload(json_path):
    with open(json_path, "r", encoding="utf-8") as file:
        payload = json.load(file)

    if "request" in payload:
        return payload["request"]
    if "metadata" in payload:
        return payload["metadata"]
    return payload


def expected_output_path_for_request(json_path, request_payload=None):
    request_payload = request_payload or load_request_payload(json_path)
    output_ext = (request_payload.get("output_ext") or "cgf").lstrip(".").lower()
    return os.path.splitext(json_path)[0] + f".{output_ext}"


def build_rc_import_command(rc_exe_path, json_path, source_fbx_path=None, output_filename=None):
    """
    Build an RC command for FBX import request JSON.

    `/overwriteextension=fbx` mirrors the CryEngine editor path: RC routes the
    JSON request through the FBX converter while the converter reads the JSON
    file itself. `/overwritesourcefile` is optional when the JSON already has a
    valid `source_filename`.
    """
    command = [
        rc_exe_path,
        json_path,
        "/overwriteextension=fbx",
    ]
    if source_fbx_path:
        command.append(f"/overwritesourcefile={source_fbx_path}")
    if output_filename:
        command.append(f"/overwritefilename={output_filename}")
    return command


class RCImportRunner:
    def __init__(self, rc_exe_path, subprocess_run=None):
        self.rc_exe_path = rc_exe_path
        self.subprocess_run = subprocess_run or subprocess.run

    def run(self, json_path, source_fbx_path=None, output_path=None):
        json_path = os.path.abspath(json_path)
        validation_error = self._validate_inputs(json_path, source_fbx_path)
        if validation_error:
            expected_output_path = output_path or os.path.splitext(json_path)[0] + ".cgf"
            output_filename = os.path.basename(expected_output_path) if expected_output_path else None
            command = build_rc_import_command(
                self.rc_exe_path,
                json_path,
                source_fbx_path=source_fbx_path,
                output_filename=output_filename,
            )
            return RCImportResult(
                success=False,
                command=command,
                json_path=json_path,
                expected_output_path=expected_output_path,
                error=validation_error,
            )

        expected_output_path = output_path or expected_output_path_for_request(json_path)
        output_filename = os.path.basename(expected_output_path) if expected_output_path else None
        command = build_rc_import_command(
            self.rc_exe_path,
            json_path,
            source_fbx_path=source_fbx_path,
            output_filename=output_filename,
        )

        try:
            completed = self.subprocess_run(
                command,
                check=False,
                capture_output=True,
                text=True,
            )
        except Exception as e:
            return RCImportResult(
                success=False,
                command=command,
                json_path=json_path,
                expected_output_path=expected_output_path,
                error=str(e),
            )

        output_exists = os.path.exists(expected_output_path)
        success = completed.returncode == 0 and output_exists
        error = ""
        if completed.returncode != 0:
            error = f"RC exited with code {completed.returncode}"
        elif not output_exists:
            error = f"Expected output was not created: {expected_output_path}"

        return RCImportResult(
            success=success,
            command=command,
            json_path=json_path,
            expected_output_path=expected_output_path,
            returncode=completed.returncode,
            stdout=completed.stdout or "",
            stderr=completed.stderr or "",
            error=error,
        )

    def _validate_inputs(self, json_path, source_fbx_path=None):
        if not self.rc_exe_path:
            return "RC executable path is not configured"
        if not os.path.exists(self.rc_exe_path):
            return f"RC executable not found: {self.rc_exe_path}"
        if not os.path.exists(json_path):
            return f"RC request JSON not found: {json_path}"
        if source_fbx_path and not os.path.exists(source_fbx_path):
            return f"Source FBX not found: {source_fbx_path}"
        return ""
