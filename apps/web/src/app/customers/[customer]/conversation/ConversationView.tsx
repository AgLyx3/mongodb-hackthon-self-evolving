"use client";

import { useEffect, useRef, useState } from "react";
import type { ConversationMessage } from "@/lib/api";
import { MessageRow } from "./MessageRow";

// Replay pacing at 1×, in ms per message. Chosen for readability, not recorded wall-clock.
const DELAY: Record<string, number> = {
  round_start: 1200,
  retro: 2200,
  lesson: 1600,
  tool_call: 600,
  tool_result: 500,
  finding: 1600,
  proposal: 2000,
  revision: 2000,
  gate: 500,
  decision: 1600,
  promotion: 1000,
  no_decision: 800,
  round_result: 1600,
};
const SPEEDS = [0.5, 1, 2, 4];

const button = {
  font: "inherit",
  padding: "var(--space-1) var(--space-3)",
  borderRadius: "var(--radius-sm)",
  border: "1px solid var(--color-border-strong)",
  background: "var(--color-surface-raised)",
  color: "var(--color-content)",
  cursor: "pointer",
};

export function ConversationView({ messages }: { messages: ConversationMessage[] }) {
  const [shown, setShown] = useState(messages.length);
  const [isPlaying, setIsPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const scroller = useRef<HTMLDivElement>(null);
  const rounds = [...new Set(messages.map((m) => m.round))];
  const n = messages.length;
  const playing = isPlaying && shown < n;

  useEffect(() => {
    if (!playing) return;
    const t = setTimeout(() => setShown((s) => s + 1), (DELAY[messages[shown].kind] ?? 800) / speed);
    return () => clearTimeout(t);
  }, [playing, shown, speed, messages]);

  useEffect(() => {
    const el = scroller.current;
    if (!playing || !el) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    el.scrollTo({ top: el.scrollHeight, behavior: reduce ? "auto" : "smooth" });
  }, [shown, playing]);

  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      const tag = (e.target as HTMLElement).tagName;
      if (e.code !== "Space" || tag === "BUTTON" || tag === "SELECT" || tag === "SUMMARY") return;
      e.preventDefault();
      handlePlayPause();
    }
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  });

  function handlePlayPause() {
    if (playing) return setIsPlaying(false);
    if (shown >= n) setShown(0);
    setIsPlaying(true);
  }

  function handleRound(r: number) {
    const first = messages.findIndex((m) => m.round === r);
    if (playing || shown <= first) {
      setShown(first);
      setIsPlaying(true);
      return;
    }
    document.getElementById(`round-${r}`)?.scrollIntoView({ block: "start" });
  }

  const current = messages[Math.max(0, shown - 1)];

  return (
    <div>
      <div
        role="toolbar"
        aria-label="Replay controls"
        style={{
          display: "flex",
          alignItems: "center",
          gap: "var(--space-3)",
          flexWrap: "wrap",
          padding: "var(--space-2) 0",
          borderBottom: "1px solid var(--color-border)",
        }}
      >
        <button type="button" style={button} onClick={handlePlayPause}>
          {playing ? "Pause" : shown >= n ? "Replay from start" : "Resume"}
        </button>
        <button
          type="button"
          style={button}
          onClick={() => {
            setIsPlaying(false);
            setShown(n);
          }}
        >
          Show all
        </button>
        <label>
          <span className="muted">Speed </span>
          <select
            value={speed}
            onChange={(e) => setSpeed(Number(e.target.value))}
            style={{ ...button, padding: "var(--space-1) var(--space-2)" }}
          >
            {SPEEDS.map((s) => (
              <option key={s} value={s}>
                {s}×
              </option>
            ))}
          </select>
        </label>
        <nav aria-label="Jump to round" style={{ display: "flex", gap: "var(--space-2)" }}>
          <span className="muted">Round</span>
          {rounds.map((r) => (
            <button
              key={r}
              type="button"
              onClick={() => handleRound(r)}
              aria-current={current?.round === r ? "step" : undefined}
              style={{
                ...button,
                padding: "0 var(--space-2)",
                borderColor: current?.round === r ? "var(--color-primary)" : "var(--color-border)",
              }}
            >
              {r}
            </button>
          ))}
        </nav>
        <span className="muted num" style={{ marginLeft: "auto" }}>
          {shown} / {n} messages · space to play or pause
        </span>
      </div>
      <div
        ref={scroller}
        onWheel={(e) => {
          if (playing && e.deltaY < 0) setIsPlaying(false);
        }}
        style={{ height: "calc(100vh - var(--space-16) * 4)", overflowY: "auto", paddingRight: "var(--space-2)" }}
      >
        {messages.slice(0, shown).map((m) => (
          <MessageRow key={m.seq} m={m} />
        ))}
        {playing ? (
          <p className="muted" aria-live="polite" style={{ padding: "var(--space-2) 0" }}>
            {messages[shown] ? `${labelFor(messages[shown])}…` : ""}
          </p>
        ) : null}
      </div>
    </div>
  );
}

function labelFor(m: ConversationMessage): string {
  switch (m.actor) {
    case "investigator":
      return "Investigator is working";
    case "tool":
    case "customer":
      return "Waiting for the result";
    case "proposer":
      return "Proposer is drafting";
    case "gates":
      return "Gates are running";
    case "fde":
      return "FDE is reviewing";
    default:
      return "";
  }
}
