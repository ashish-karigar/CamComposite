import queue
import shutil
import subprocess
import sys
import threading
import tempfile
import time
from pathlib import Path

import cv2


class _AudioRecorder:
    """Capture the default microphone into a temporary WAV file."""

    SAMPLE_RATE = 48_000
    CHANNELS = 1

    def __init__(self, output_path):
        try:
            import sounddevice as sd
            import soundfile as sf
        except ImportError as exc:
            raise RuntimeError(
                "Install sounddevice and soundfile to record audio."
            ) from exc

        self.sd = sd
        self.sf = sf
        self.output_path = Path(output_path)
        self.audio_file = None
        self.stream = None
        self.audio_queue = queue.Queue(maxsize=32)
        self.stop_requested = threading.Event()
        self.worker = None
        self.dropped_chunks = 0

    def start(self):
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.audio_file = self.sf.SoundFile(
            str(self.output_path),
            mode="w",
            samplerate=self.SAMPLE_RATE,
            channels=self.CHANNELS,
            subtype="PCM_16",
        )

        self.worker = threading.Thread(
            target=self._writer_loop,
            name="CamCompositeAudioWriter",
            daemon=True,
        )
        self.worker.start()

        try:
            self.stream = self.sd.InputStream(
                samplerate=self.SAMPLE_RATE,
                channels=self.CHANNELS,
                dtype="float32",
                callback=self._audio_callback,
            )
            self.stream.start()
        except Exception:
            self.stop()
            raise

    def stop(self):
        if self.stream is not None:
            try:
                self.stream.stop()
            finally:
                self.stream.close()
            self.stream = None

        self.stop_requested.set()
        if self.worker is not None:
            self.worker.join(timeout=5)
            self.worker = None

        if self.audio_file is not None:
            self.audio_file.close()
            self.audio_file = None

    def _audio_callback(self, indata, _frames, _time_info, _status):
        try:
            self.audio_queue.put_nowait(indata.copy())
        except queue.Full:
            self.dropped_chunks += 1

    def _writer_loop(self):
        while True:
            try:
                chunk = self.audio_queue.get(timeout=0.1)
            except queue.Empty:
                if self.stop_requested.is_set():
                    break
                continue

            try:
                self.audio_file.write(chunk)
            except Exception:
                break


class RecordingService:
    """Record the composited BGR stream with real-time pacing and audio."""

    def __init__(self, output_w, output_h, output_fps):
        self.output_w = int(output_w)
        self.output_h = int(output_h)
        self.output_fps = float(output_fps)
        self.frame_period = 1.0 / max(self.output_fps, 1.0)

        self.writer = None
        self.output_path = None
        self.temp_dir = None
        self.video_path = None
        self.audio_path = None
        self.audio_recorder = None
        self.ffmpeg_path = None
        self.frame_queue = None
        self.worker = None
        self.stop_requested = None
        self.active = False
        self.frames_written = 0
        self.frames_dropped = 0
        self.error = None
        self.audio_warning = None
        self.next_frame_time = None

    def start(self):
        if self.is_recording():
            raise RuntimeError("Recording is already active.")

        if self.has_pending_recording():
            raise RuntimeError("Save or discard the previous recording first.")

        self.temp_dir = Path(tempfile.mkdtemp(prefix="camcomposite-recording-"))
        path = self.temp_dir / "video.mp4"

        self.output_path = None
        self.video_path = path
        self.audio_path = None
        self.audio_recorder = None
        self.ffmpeg_path = self._find_ffmpeg()
        self.audio_warning = None

        if self.ffmpeg_path is not None:
            audio_path = self.temp_dir / "audio.wav"
            try:
                audio_recorder = _AudioRecorder(audio_path)
                audio_recorder.start()
                self.audio_recorder = audio_recorder
                self.audio_path = audio_path
            except Exception as exc:
                self.audio_warning = str(exc)
                self._cleanup_temp_audio(audio_path)
        else:
            self.audio_warning = "FFmpeg was not found; recording will not include audio."

        writer = cv2.VideoWriter(
            str(self.video_path),
            cv2.VideoWriter_fourcc(*"mp4v"),
            self.output_fps,
            (self.output_w, self.output_h),
        )

        if not writer.isOpened():
            writer.release()
            self._stop_audio_capture()
            self._cleanup_temp_files()
            raise RuntimeError("Could not open the selected file for recording.")

        self.writer = writer
        self.frame_queue = queue.Queue(maxsize=8)
        self.stop_requested = threading.Event()
        self.active = True
        self.frames_written = 0
        self.frames_dropped = 0
        self.error = None
        self.next_frame_time = None

        self.worker = threading.Thread(
            target=self._writer_loop,
            name="CamCompositeRecorder",
            daemon=True,
        )
        self.worker.start()

    def submit(self, frame_bgr):
        if not self.is_recording() or frame_bgr is None:
            return

        try:
            frame = frame_bgr
            if frame.shape[1] != self.output_w or frame.shape[0] != self.output_h:
                frame = cv2.resize(
                    frame,
                    (self.output_w, self.output_h),
                    interpolation=cv2.INTER_AREA,
                )

            # VideoWriter has no timestamps. Emit the number of frame slots
            # that elapsed since the previous callback so a slow capture loop
            # does not create an accidentally fast (2x) recording.
            now = time.monotonic()
            if self.next_frame_time is None:
                self.next_frame_time = now

            slots = 0
            while now >= self.next_frame_time and slots < 8:
                slots += 1
                self.next_frame_time += self.frame_period

            if slots == 0:
                return

            # The composed frame is immutable after this callback. One owned
            # copy can safely back multiple elapsed frame slots.
            owned_frame = frame.copy()
            for _ in range(slots):
                try:
                    self.frame_queue.put_nowait(owned_frame)
                except queue.Full:
                    self.frames_dropped += 1
                    break
        except Exception as exc:
            self.error = exc

    def stop(self):
        if not self.is_recording():
            return

        self.stop_requested.set()

        if self.worker is not None:
            self.worker.join(timeout=5)

        if self.worker is not None and self.worker.is_alive():
            self._release_writer()

        self.worker = None
        self.frame_queue = None
        self.stop_requested = None
        self.active = False

        self._stop_audio_capture()

    def finalize(self, output_path):
        if self.is_recording():
            raise RuntimeError("Stop the recording before saving it.")

        if not self.has_pending_recording():
            raise RuntimeError("There is no pending recording to save.")

        saved_path = Path(output_path).expanduser()
        self.output_path = saved_path
        saved_path.parent.mkdir(parents=True, exist_ok=True)
        self._finish_file()
        return saved_path

    def discard(self):
        if self.is_recording():
            self.stop()

        self._cleanup_temp_files()

    def has_pending_recording(self):
        return (
            not self.is_recording()
            and self.video_path is not None
            and self.video_path.exists()
        )

    def is_recording(self):
        return self.active

    def _writer_loop(self):
        while True:
            try:
                frame = self.frame_queue.get(timeout=0.1)
            except queue.Empty:
                if self.stop_requested.is_set():
                    break
                continue

            try:
                self.writer.write(frame)
                self.frames_written += 1
            except Exception as exc:
                self.error = exc
                break

        self._release_writer()

    def _release_writer(self):
        writer = self.writer
        self.writer = None

        if writer is not None:
            try:
                writer.release()
            except Exception:
                pass

    def _stop_audio_capture(self):
        if self.audio_recorder is not None:
            try:
                self.audio_recorder.stop()
            except Exception as exc:
                self.audio_warning = str(exc)
            self.audio_recorder = None

    def _finish_file(self):
        if self.video_path is None or self.output_path is None:
            return

        if self.audio_path is not None and self.ffmpeg_path is not None:
            try:
                subprocess.run(
                    [
                        str(self.ffmpeg_path),
                        "-y",
                        "-i",
                        str(self.video_path),
                        "-i",
                        str(self.audio_path),
                        "-map",
                        "0:v:0",
                        "-map",
                        "1:a:0",
                        "-c:v",
                        "copy",
                        "-c:a",
                        "aac",
                        "-b:a",
                        "128k",
                        "-shortest",
                        "-movflags",
                        "+faststart",
                        str(self.output_path),
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    check=True,
                    timeout=30,
                )
            except subprocess.CalledProcessError as exc:
                detail = (exc.stderr or b"").decode("utf-8", errors="replace").strip()
                self.audio_warning = (
                    f"Audio muxing failed: {detail or 'FFmpeg returned an error.'}"
                )
                try:
                    shutil.move(str(self.video_path), str(self.output_path))
                except Exception as move_exc:
                    self.error = move_exc
            except Exception as exc:
                self.audio_warning = f"Audio muxing failed: {exc}"
                try:
                    shutil.move(str(self.video_path), str(self.output_path))
                except Exception as move_exc:
                    self.error = move_exc
        else:
            if self.video_path != self.output_path:
                try:
                    shutil.move(str(self.video_path), str(self.output_path))
                except Exception as exc:
                    self.error = exc

        self._cleanup_temp_files()

    def _cleanup_temp_audio(self, audio_path):
        try:
            audio_path.unlink(missing_ok=True)
        except Exception:
            pass

    def _cleanup_temp_files(self):
        for path in (self.video_path, self.audio_path):
            if path is None or path == self.output_path:
                continue
            try:
                path.unlink(missing_ok=True)
            except Exception:
                pass

        if self.temp_dir is not None:
            try:
                self.temp_dir.rmdir()
            except OSError:
                pass

        self.temp_dir = None
        self.video_path = None
        self.audio_path = None
        self.output_path = None

    @staticmethod
    def _find_ffmpeg():
        candidates = []

        bundled_root = getattr(sys, "_MEIPASS", None)
        if bundled_root:
            candidates.append(Path(bundled_root) / "assets" / "bin" / "macos" / "ffmpeg")

        project_root = Path(__file__).resolve().parents[2]
        candidates.append(project_root / "assets" / "bin" / "macos" / "ffmpeg")

        system_ffmpeg = shutil.which("ffmpeg")
        if system_ffmpeg:
            candidates.append(Path(system_ffmpeg))

        try:
            import imageio_ffmpeg

            candidates.append(Path(imageio_ffmpeg.get_ffmpeg_exe()))
        except Exception:
            pass

        for candidate in candidates:
            if not candidate.exists() or not candidate.is_file():
                continue

            try:
                subprocess.run(
                    [str(candidate), "-version"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    check=True,
                    timeout=3,
                )
                return candidate
            except Exception:
                # A bundled FFmpeg can outlive the Homebrew libraries it was
                # linked against. Skip broken binaries and try the next one.
                continue

        return None
