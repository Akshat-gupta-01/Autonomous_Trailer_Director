"""Video renderer - creates actual video files from EDL using ffmpeg."""

from __future__ import annotations

import subprocess
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List

from src.models.trailer import TrailerPlan
from src.models.story_map import StoryMap


@dataclass
class VideoRendererConfig:
    """Configuration for video rendering."""
    ffmpeg_path: str = "ffmpeg"
    video_codec: str = "libx264"
    audio_codec: str = "aac"
    crf: int = 23  # Constant Rate Factor (lower = better quality, 18-28 typical)
    preset: str = "medium"  # ultrafast, superfast, veryfast, faster, fast, medium, slow, slower, veryslow
    output_format: str = "mp4"
    keep_intermediate: bool = False


class VideoRenderer:
    """Renders actual video files from EDL using ffmpeg."""
    
    def __init__(self, config: Optional[VideoRendererConfig] = None):
        self.config = config or VideoRendererConfig()
        self._verify_ffmpeg()
    
    def _verify_ffmpeg(self) -> None:
        """Check if ffmpeg is available."""
        if not shutil.which(self.config.ffmpeg_path):
            raise RuntimeError(
                f"ffmpeg not found at '{self.config.ffmpeg_path}'. "
                "Install ffmpeg: https://ffmpeg.org/download.html"
            )
    
    def render_trailer(
        self,
        trailer: TrailerPlan,
        story_map: StoryMap,
        source_video_path: Path,
        output_path: Path,
    ) -> dict:
        """
        Render a trailer video from EDL.
        
        Args:
            trailer: TrailerPlan with segments
            story_map: StoryMap with scene info
            source_video_path: Path to source video file
            output_path: Where to write the output video
            
        Returns:
            Dict with render info
        """
        if not source_video_path.exists():
            raise FileNotFoundError(f"Source video not found: {source_video_path}")
        
        # Create segment list for ffmpeg concat
        segments = self._prepare_segments(trailer, story_map)
        
        if not segments:
            raise ValueError("No segments to render")
        
        # Write concat file
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            concat_file = tmpdir / "concat.txt"
            
            # Extract each segment to a temp file
            segment_files = []
            for i, seg in enumerate(segments):
                out_file = tmpdir / f"seg_{i:03d}.ts"  # MPEG-TS for lossless concat
                self._extract_segment(source_video_path, seg, out_file)
                segment_files.append(out_file)
            
            # Write concat list
            with open(concat_file, "w") as f:
                for sf in segment_files:
                    f.write(f"file '{sf}'\n")
            
            # Concatenate and encode
            self._concat_and_encode(concat_file, output_path)
        
        return {
            "output_path": str(output_path),
            "segments_rendered": len(segments),
            "source_video": str(source_video_path),
        }
    
    def render_all_trailers(
        self,
        trailers: List[TrailerPlan],
        story_map: StoryMap,
        source_video_path: Path,
        output_dir: Path,
    ) -> List[dict]:
        """Render all trailers in a fleet."""
        results = []
        for trailer in trailers:
            output_path = output_dir / f"{trailer.trailer_id}.{self.config.output_format}"
            try:
                result = self.render_trailer(trailer, story_map, source_video_path, output_path)
                results.append(result)
            except Exception as e:
                results.append({
                    "trailer_id": trailer.trailer_id,
                    "error": str(e),
                    "output_path": str(output_path),
                })
        return results
    
    def _prepare_segments(self, trailer: TrailerPlan, story_map: StoryMap) -> List[dict]:
        """Convert trailer segments to render instructions."""
        segments = []
        for segment in trailer.segments:
            seg_info = {
                "segment_id": segment.segment_id,
                "start_ms": segment.source_in.normalised_ms,
                "end_ms": segment.source_out.normalised_ms,
                "duration_ms": segment.duration_ms,
            }
            segments.append(seg_info)
        return segments
    
    def _extract_segment(self, source: Path, seg: dict, output: Path) -> None:
        """Extract a single segment using ffmpeg."""
        start_sec = seg["start_ms"] / 1000.0
        duration_sec = seg["duration_ms"] / 1000.0
        
        cmd = [
            self.config.ffmpeg_path,
            "-y",  # overwrite
            "-ss", str(start_sec),
            "-t", str(duration_sec),
            "-i", str(source),
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "18",
            "-c:a", "aac",
            "-b:a", "128k",
            "-f", "mpegts",  # MPEG-TS for lossless concat
            str(output),
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg extract failed: {result.stderr}")
    
    def _concat_and_encode(self, concat_file: Path, output: Path) -> None:
        """Concatenate segments and encode final video."""
        cmd = [
            self.config.ffmpeg_path,
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_file),
            "-c:v", self.config.video_codec,
            "-preset", self.config.preset,
            "-crf", str(self.config.crf),
            "-c:a", self.config.audio_codec,
            "-b:a", "192k",
            "-movflags", "+faststart",  # Web optimization
            str(output),
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg concat failed: {result.stderr}")


def render_video_from_edl(
    trailer: TrailerPlan,
    story_map: StoryMap,
    source_video: Path,
    output_path: Path,
    config: Optional[VideoRendererConfig] = None,
) -> dict:
    """Convenience function to render a single trailer video."""
    renderer = VideoRenderer(config)
    return renderer.render_trailer(trailer, story_map, source_video, output_path)