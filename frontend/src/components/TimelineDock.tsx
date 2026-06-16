import * as Slider from "@radix-ui/react-slider";
import { Pause, Play, SkipBack, SkipForward } from "lucide-react";
import { useEffect, useMemo } from "react";
import { WindowPreset } from "../ws/replay";
import { formatUtc, formatUtcDate, fromMs, toMs } from "../utils/time";

type TimelineDockProps = {
  playing: boolean;
  current: string;
  start: string;
  end: string;
  dataStart: string;
  dataEnd: string;
  windowPreset: WindowPreset;
  windowPresets: WindowPreset[];
  speed: number;
  onPlay: () => void;
  onPause: () => void;
  onSeek: (t: string) => void;
  onWindowPreset: (preset: WindowPreset) => void;
  onSpeed: (multiplier: number) => void;
};

const SPEEDS = [1, 2, 5, 10] as const;
const SCRUB_STEP_MS = 60_000;
const MS_PER_HOUR = 3_600_000;

function formatDataSpan(dataStartMs: number, dataEndMs: number): string {
  const hours = Math.max(1, Math.round((dataEndMs - dataStartMs) / MS_PER_HOUR));
  if (hours < 48) return `${hours}h stored`;
  const days = Math.round(hours / 24);
  return `${days}d stored`;
}

export function TimelineDock({
  playing,
  current,
  start,
  end,
  dataStart,
  dataEnd,
  windowPreset,
  windowPresets,
  speed,
  onPlay,
  onPause,
  onSeek,
  onWindowPreset,
  onSpeed,
}: TimelineDockProps) {
  const startMs = toMs(start);
  const endMs = toMs(end);
  const dataStartMs = toMs(dataStart);
  const dataEndMs = toMs(dataEnd);
  const currentMs = Math.min(Math.max(toMs(current), startMs), endMs);
  const dataSpanLabel = useMemo(
    () => formatDataSpan(dataStartMs, dataEndMs),
    [dataStartMs, dataEndMs],
  );

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLSelectElement) return;
      if (e.code === "Space") {
        e.preventDefault();
        playing ? onPause() : onPlay();
      } else if (e.code === "ArrowLeft") {
        e.preventDefault();
        onSeek(fromMs(Math.max(startMs, currentMs - SCRUB_STEP_MS)));
      } else if (e.code === "ArrowRight") {
        e.preventDefault();
        onSeek(fromMs(Math.min(endMs, currentMs + SCRUB_STEP_MS)));
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [playing, onPlay, onPause, onSeek, startMs, endMs, currentMs]);

  return (
    <footer className="timeline-dock">
      <div className="timeline-dock__controls">
        <button
          type="button"
          className="timeline-btn"
          title="Step back 1 min (←)"
          onClick={() => onSeek(fromMs(Math.max(startMs, currentMs - SCRUB_STEP_MS)))}
        >
          <SkipBack size={16} />
        </button>
        <button
          type="button"
          className="timeline-btn timeline-btn--primary"
          title={playing ? "Pause (Space)" : "Play (Space)"}
          onClick={playing ? onPause : onPlay}
        >
          {playing ? <Pause size={18} /> : <Play size={18} />}
        </button>
        <button
          type="button"
          className="timeline-btn"
          title="Step forward 1 min (→)"
          onClick={() => onSeek(fromMs(Math.min(endMs, currentMs + SCRUB_STEP_MS)))}
        >
          <SkipForward size={16} />
        </button>
      </div>

      <div className="timeline-dock__track">
        <div className="timeline-dock__range-labels">
          <span>{formatUtcDate(start)}</span>
          <span className="timeline-dock__window-hint">
            {windowPreset} window · {dataSpanLabel}
          </span>
          <span>{formatUtcDate(end)}</span>
        </div>
        <Slider.Root
          className="timeline-slider"
          min={startMs}
          max={endMs}
          step={1000}
          value={[currentMs]}
          onValueChange={([value]) => onSeek(fromMs(value))}
        >
          <Slider.Track className="timeline-slider__track">
            <Slider.Range className="timeline-slider__range" />
          </Slider.Track>
          <Slider.Thumb className="timeline-slider__thumb" aria-label="Scenario time" />
        </Slider.Root>
        <time className="timeline-dock__current">{formatUtc(current)}</time>
      </div>

      <div className="timeline-dock__window">
        <span className="timeline-dock__window-label">Window</span>
        <div className="window-buttons">
          {windowPresets.map((preset) => (
            <button
              key={preset}
              type="button"
              className={`window-btn ${windowPreset === preset ? "window-btn--active" : ""}`}
              onClick={() => onWindowPreset(preset)}
            >
              {preset}
            </button>
          ))}
        </div>
      </div>

      <div className="timeline-dock__speed">
        <span className="timeline-dock__speed-label">Speed</span>
        <div className="speed-buttons">
          {SPEEDS.map((s) => (
            <button
              key={s}
              type="button"
              className={`speed-btn ${speed === s ? "speed-btn--active" : ""}`}
              onClick={() => onSpeed(s)}
            >
              {s}×
            </button>
          ))}
        </div>
      </div>
    </footer>
  );
}
