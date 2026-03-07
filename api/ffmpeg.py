import os
import shutil
import signal
import subprocess
import threading
import time
from typing import Dict, Optional


class FFmpegManager:
    def __init__(self, hls_dir: str, public_hls_base: str) -> None:
        self.hls_dir = hls_dir
        self.public_hls_base = public_hls_base.rstrip("/")
        self._lock = threading.Lock()
        self._procs: Dict[str, subprocess.Popen] = {}
        self._last_error: Dict[str, Optional[str]] = {}
        self._status: Dict[str, str] = {}
        self._started_at: Dict[str, Optional[int]] = {}
        self._last_seen_at: Dict[str, Optional[int]] = {}
        self._restart_count: Dict[str, int] = {}

        os.makedirs(os.path.join(self.hls_dir, "live"), exist_ok=True)
        os.makedirs("/data", exist_ok=True)

    def hls_url(self, channel_id: str) -> str:
        return f"{self.public_hls_base}/live/{channel_id}/index.m3u8"

    def log_path(self, channel_id: str) -> str:
        return f"/data/ffmpeg_{channel_id}.log"

    def _channel_dir(self, channel_id: str) -> str:
        return os.path.join(self.hls_dir, "live", channel_id)

    def _playlist_path(self, channel_id: str) -> str:
        return os.path.join(self._channel_dir(channel_id), "index.m3u8")

    def is_running(self, channel_id: str) -> bool:
        with self._lock:
            p = self._procs.get(channel_id)
            return bool(p and p.poll() is None)

    def status(self, channel_id: str) -> str:
        with self._lock:
            return self._status.get(channel_id, "stopped")

    def last_error(self, channel_id: str) -> Optional[str]:
        with self._lock:
            return self._last_error.get(channel_id)

    def started_at(self, channel_id: str) -> Optional[int]:
        with self._lock:
            return self._started_at.get(channel_id)

    def last_seen_at(self, channel_id: str) -> Optional[int]:
        with self._lock:
            return self._last_seen_at.get(channel_id)

    def restart_count(self, channel_id: str) -> int:
        with self._lock:
            return int(self._restart_count.get(channel_id, 0))

    def _set_error(self, channel_id: str, message: Optional[str]) -> None:
        self._last_error[channel_id] = message

    def _set_status(self, channel_id: str, status: str) -> None:
        self._status[channel_id] = status

    def _touch_seen(self, channel_id: str) -> None:
        self._last_seen_at[channel_id] = int(time.time())

    def _reset_channel_dir(self, channel_id: str) -> None:
        ch_dir = self._channel_dir(channel_id)
        if os.path.isdir(ch_dir):
            shutil.rmtree(ch_dir, ignore_errors=True)
        os.makedirs(ch_dir, exist_ok=True)

    def _base_cmd(self, source_url: str, seg_pattern: str, out_m3u8: str) -> list[str]:
        return [
            "ffmpeg",
            "-hide_banner",
            "-nostdin",
            "-loglevel",
            "warning",
            "-fflags",
            "+genpts",
            "-rw_timeout",
            "15000000",
            "-i",
            source_url,
            "-max_muxing_queue_size",
            "2048",
            "-f",
            "hls",
            "-hls_time",
            "4",
            "-hls_list_size",
            "10",
            "-hls_flags",
            "delete_segments+append_list+independent_segments",
            "-hls_segment_filename",
            seg_pattern,
            out_m3u8,
        ]

    def _build_cmd(self, source_url: str, profile: str, seg_pattern: str, out_m3u8: str) -> list[str]:
        base = self._base_cmd(source_url, seg_pattern, out_m3u8)
        insert_at = base.index("-f")

        if profile == "transcode_720p":
            extra = [
                "-vf", "scale=-2:720",
                "-c:v", "libx264",
                "-preset", "veryfast",
                "-tune", "zerolatency",
                "-pix_fmt", "yuv420p",
                "-b:v", "2500k",
                "-maxrate", "2800k",
                "-bufsize", "5000k",
                "-c:a", "aac",
                "-b:a", "128k",
                "-ac", "2",
                "-ar", "48000",
            ]
        elif profile == "transcode_480p":
            extra = [
                "-vf", "scale=-2:480",
                "-c:v", "libx264",
                "-preset", "veryfast",
                "-tune", "zerolatency",
                "-pix_fmt", "yuv420p",
                "-b:v", "1200k",
                "-maxrate", "1400k",
                "-bufsize", "2400k",
                "-c:a", "aac",
                "-b:a", "128k",
                "-ac", "2",
                "-ar", "48000",
            ]
        elif profile == "audio_aac_fix":
            extra = [
                "-c:v", "copy",
                "-c:a", "aac",
                "-b:a", "128k",
                "-ac", "2",
                "-ar", "48000",
            ]
        else:
            extra = [
                "-c:v", "copy",
                "-c:a", "copy",
            ]

        return base[:insert_at] + extra + base[insert_at:]

    def _run_cmd(self, channel_id: str, cmd: list[str]) -> subprocess.Popen:
        log_path = self.log_path(channel_id)
        with open(log_path, "ab") as lf:
            lf.write(b"\n\n=== START CMD ===\n")
            lf.write((" ".join(cmd) + "\n").encode("utf-8", "ignore"))

        lf = open(log_path, "ab")
        return subprocess.Popen(
            cmd,
            stdout=lf,
            stderr=lf,
            preexec_fn=os.setsid if hasattr(os, "setsid") else None,
        )

    def _probe_started(self, channel_id: str, seconds: int = 12) -> bool:
        out_m3u8 = self._playlist_path(channel_id)
        deadline = time.time() + seconds

        while time.time() < deadline:
            p = self._procs.get(channel_id)
            if p and p.poll() is not None:
                return False
            if os.path.exists(out_m3u8) and os.path.getsize(out_m3u8) > 0:
                self._touch_seen(channel_id)
                return True
            time.sleep(0.5)

        return False

    def start(self, channel_id: str, source_url: str, profile: str = "copy") -> None:
        with self._lock:
            self._stop_nolock(channel_id)
            self._reset_channel_dir(channel_id)
            self._set_error(channel_id, None)
            self._set_status(channel_id, "starting")
            self._started_at[channel_id] = int(time.time())

            ch_dir = self._channel_dir(channel_id)
            out_m3u8 = os.path.join(ch_dir, "index.m3u8")
            seg_pattern = os.path.join(ch_dir, "seg_%05d.ts")

            cmd = self._build_cmd(source_url, profile, seg_pattern, out_m3u8)
            p = self._run_cmd(channel_id, cmd)
            self._procs[channel_id] = p

        ok = self._probe_started(channel_id, seconds=10)
        if ok:
            with self._lock:
                self._set_status(channel_id, "running")
            return

        fallback_profile = "audio_aac_fix" if profile == "copy" else "transcode_480p"

        with self._lock:
            self._stop_nolock(channel_id)
            self._restart_count[channel_id] = int(self._restart_count.get(channel_id, 0)) + 1
            self._set_status(channel_id, "starting")
            ch_dir = self._channel_dir(channel_id)
            out_m3u8 = os.path.join(ch_dir, "index.m3u8")
            seg_pattern = os.path.join(ch_dir, "seg_%05d.ts")
            cmd = self._build_cmd(source_url, fallback_profile, seg_pattern, out_m3u8)
            p = self._run_cmd(channel_id, cmd)
            self._procs[channel_id] = p

        ok = self._probe_started(channel_id, seconds=12)
        if ok:
            with self._lock:
                self._set_status(channel_id, "running")
            return

        with self._lock:
            self._set_error(channel_id, "ffmpeg failed to produce HLS output")
            self._set_status(channel_id, "error")
            self._stop_nolock(channel_id)

    def stop(self, channel_id: str) -> None:
        with self._lock:
            self._stop_nolock(channel_id)
            self._set_status(channel_id, "stopped")

    def _stop_nolock(self, channel_id: str) -> None:
        p: Optional[subprocess.Popen] = self._procs.get(channel_id)
        if not p:
            return

        if p.poll() is not None:
            self._procs.pop(channel_id, None)
            return

        try:
            if hasattr(os, "killpg") and hasattr(os, "getpgid"):
                os.killpg(os.getpgid(p.pid), signal.SIGTERM)
            else:
                p.terminate()
        except Exception:
            pass

        try:
            p.wait(timeout=5)
        except Exception:
            try:
                if hasattr(os, "killpg") and hasattr(os, "getpgid"):
                    os.killpg(os.getpgid(p.pid), signal.SIGKILL)
                else:
                    p.kill()
            except Exception:
                pass

        self._procs.pop(channel_id, None)

    def read_log_tail(self, channel_id: str, lines: int = 80) -> str:
        path = self.log_path(channel_id)
        if not os.path.exists(path):
            return ""

        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                data = f.readlines()
            return "".join(data[-lines:])
        except Exception as e:
            return f"failed to read log: {e}"

    def metrics(self, channel_id: str) -> Dict[str, Optional[int] | str | bool]:
        playlist = self._playlist_path(channel_id)
        playlist_exists = os.path.exists(playlist)
        playlist_mtime = int(os.path.getmtime(playlist)) if playlist_exists else None

        segment_count = 0
        ch_dir = self._channel_dir(channel_id)
        if os.path.isdir(ch_dir):
            try:
                segment_count = len([x for x in os.listdir(ch_dir) if x.endswith(".ts")])
            except Exception:
                segment_count = 0

        if playlist_exists:
            with self._lock:
                self._touch_seen(channel_id)

        return {
            "status": self.status(channel_id),
            "running": self.is_running(channel_id),
            "last_error": self.last_error(channel_id),
            "started_at": self.started_at(channel_id),
            "last_seen_at": self.last_seen_at(channel_id),
            "restart_count": self.restart_count(channel_id),
            "playlist_exists": playlist_exists,
            "playlist_mtime": playlist_mtime,
            "segment_count": segment_count,
            "hls_url": self.hls_url(channel_id),
        }
