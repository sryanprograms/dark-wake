import * as Slider from "@radix-ui/react-slider";
import { Pause, Play, Radio, SkipBack, SkipForward, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { formatTimelineSpan } from "../utils/timelineCoverage";
import { formatUtc, formatUtcDate, fromMs, toMs } from "../utils/time";
import { LIVE_EDGE_MS } from "../constants/timeline";
import type { PlayheadMode, TimelineScene } from "../ws/timeline";

type TimelineDockProps = {
  playing: boolean;
  current: string;
  dataStart: string;
  liveEdge: string;
  playheadMode: PlayheadMode;
  scenes: TimelineScene[];
  currentSceneId: string | null;
  positionCount: number | null;
  speed: number;
  onPlay: () => void;
  onPause: () => void;
  onSeek: (t: string) => void;
  onGoLive: () => void;
  onSceneClick: (sceneId: string) => void;
  onSpeed: (multiplier: number) => void;
};

const SPEEDS = [1, 2, 5, 10] as const;
const SCRUB_STEP_MS = 60_000;

function modeStatusLabel(mode: PlayheadMode): string {
  if (mode === "live") return "LIVE";
  if (mode === "scene") return "SAR SCENE";
  return "HISTORICAL";
}

function modeStatusClass(mode: PlayheadMode): string {
  if (mode === "live") return "timeline-dock__status--live";
  if (mode === "scene") return "timeline-dock__status--scene";
  return "timeline-dock__status--historical";
}

export function TimelineDock({
  playing,
  current,
  dataStart,
  liveEdge,
  playheadMode,
  scenes,
  currentSceneId,
  positionCount,
  speed,
  onPlay,
  onPause,
  onSeek,
  onGoLive,
  onSceneClick,
  onSpeed,
}: TimelineDockProps) {
  const startMs = toMs(dataStart);
  const endMs = toMs(liveEdge);
  const [scrubMs, setScrubMs] = useState(() => toMs(current));
  const currentMs = Math.min(Math.max(toMs(current), startMs), endMs);
  const spanMs = Math.max(endMs - startMs, 1);
  const dataSpanLabel = useMemo(
    () => `${formatTimelineSpan(dataStart, liveEdge)} span`,
    [dataStart, liveEdge],
  );
  const coverageHint =
    positionCount != null ? `${positionCount.toLocaleString()} stored positions` : null;
  const playDisabled = playheadMode === "live" || playheadMode === "scene";

  useEffect(() => {
    setScrubMs(currentMs);
  }, [currentMs]);

  const sceneMarkers = useMemo(
    () =>
      scenes.map((scene) => ({
        ...scene,
        pct: ((toMs(scene.t) - startMs) / spanMs) * 100,
      })),
    [scenes, startMs, spanMs],
  );

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLSelectElement) return;
      if (e.code === "Space") {
        e.preventDefault();
        if (playDisabled) return;
        playing ? onPause() : onPlay();
      } else if (e.code === "ArrowLeft") {
        e.preventDefault();
        onSeek(fromMs(Math.max(startMs, currentMs - SCRUB_STEP_MS)));
      } else if (e.code === "ArrowRight") {
        e.preventDefault();
        const next = Math.min(endMs, currentMs + SCRUB_STEP_MS);
        if (endMs - next <= LIVE_EDGE_MS) {
          onGoLive();
        } else {
          onSeek(fromMs(next));
        }
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [playing, onPlay, onPause, onSeek, onGoLive, startMs, endMs, currentMs, playDisabled]);

  const commitSeek = (ms: number) => {
    if (endMs - ms <= LIVE_EDGE_MS) {
      onGoLive();
      return;
    }
    onSeek(fromMs(ms));
  };

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
          title={playDisabled ? "Playback applies to historical data" : playing ? "Pause (Space)" : "Play (Space)"}
          disabled={playDisabled}
          onClick={playing ? onPause : onPlay}
        >
          {playing ? <Pause size={18} /> : <Play size={18} />}
        </button>
        <button
          type="button"
          className="timeline-btn"
          title="Step forward 1 min (→)"
          onClick={() => {
            const next = Math.min(endMs, currentMs + SCRUB_STEP_MS);
            if (endMs - next <= LIVE_EDGE_MS) onGoLive();
            else onSeek(fromMs(next));
          }}
        >
          <SkipForward size={16} />
        </button>
        <button
          type="button"
          className={`timeline-btn timeline-btn--live${playheadMode === "live" ? " timeline-btn--live-active" : ""}`}
          title={playheadMode === "scene" ? "Exit SAR scene and return to live" : "Jump to live edge"}
          onClick={onGoLive}
        >
          <Radio size={16} />
        </button>
        {playheadMode === "scene" ? (
          <button
            type="button"
            className="timeline-btn timeline-btn--scene-exit"
            title="Exit SAR scene and return to live monitoring"
            onClick={onGoLive}
          >
            <X size={14} />
            <span>Exit scene</span>
          </button>
        ) : null}
      </div>

      <div className="timeline-dock__track">
        <div className="timeline-dock__range-labels">
          <span>{formatUtcDate(dataStart)}</span>
          <span className={`timeline-dock__status ${modeStatusClass(playheadMode)}`}>
            {modeStatusLabel(playheadMode)}
          </span>
          <span className="timeline-dock__window-hint">
            {dataSpanLabel}
            {coverageHint ? ` · ${coverageHint}` : ""}
          </span>
          <span>{formatUtcDate(liveEdge)}</span>
        </div>
        <div className="timeline-slider-wrap">
          <div className="timeline-scene-markers" aria-hidden={scenes.length === 0}>
            {sceneMarkers.map((scene) => (
              <button
                key={scene.id}
                type="button"
                className={`timeline-scene-marker${currentSceneId === String(scene.id) ? " timeline-scene-marker--active" : ""}`}
                style={{ left: `${Math.min(100, Math.max(0, scene.pct))}%` }}
                title={`SAR scene · ${formatUtc(scene.t)}${scene.dark_count ? ` · ${scene.dark_count} dark` : ""}`}
                onClick={(e) => {
                  e.stopPropagation();
                  onSceneClick(String(scene.id));
                }}
              />
            ))}
          </div>
          <Slider.Root
            className="timeline-slider"
            min={startMs}
            max={endMs}
            step={1000}
            value={[scrubMs]}
            onValueChange={([value]) => setScrubMs(value)}
            onValueCommit={([value]) => commitSeek(value)}
          >
            <Slider.Track className="timeline-slider__track">
              <Slider.Range className="timeline-slider__range" />
            </Slider.Track>
            <Slider.Thumb className="timeline-slider__thumb" aria-label="Playhead time" />
          </Slider.Root>
        </div>
        <time className="timeline-dock__current">{formatUtc(current)}</time>
      </div>

      <div className="timeline-dock__speed">
        <span className="timeline-dock__speed-label">Playback speed</span>
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
