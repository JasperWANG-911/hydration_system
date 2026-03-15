import { useState, useEffect, useRef } from "react";

// ── Palette matching the project ──
const NAVY = "#0A2342";
const TEAL = "#028090";
const SEAFOAM = "#00A896";
const MINT = "#D6F0ED";
const CREAM = "#F2EFE9";
const SLATE = "#4A5568";
const AMBER = "#F39C12";
const RED = "#E74C3C";
const GREEN = "#2ECC71";
const GREY = "#95A5A6";

// ── Template patients ──
const INITIAL_BEDS = [
  { id: "A01", name: "Bed A01", events: [], risk: "AKI",       wakeHour: 7  },
  { id: "A02", name: "Bed A02", events: [], risk: "Post-op",   wakeHour: 7  },
  { id: "A03", name: "Bed A03", events: [], risk: "Elderly",   wakeHour: 8  },
  { id: "A04", name: "Bed A04", events: [], risk: "MCI",       wakeHour: 7  },
  { id: "B01", name: "Bed B01", events: [], risk: "Post-op",   wakeHour: 7  },
  { id: "B02", name: "Bed B02", events: [], risk: "AKI",       wakeHour: 7  },
  { id: "B03", name: "Bed B03", events: [], risk: "Elderly",   wakeHour: 8  },
  { id: "B04", name: "Bed B04", events: [], risk: "Care home", wakeHour: 8  },
];

// Scenario presets — realistic intake profiles
const SCENARIOS = {
  "Good morning drinker": [
    { h: 7.5, ml: 180 }, { h: 8.5, ml: 150 }, { h: 9.5, ml: 160 },
    { h: 10.5, ml: 140 }, { h: 11.5, ml: 130 }, { h: 13.0, ml: 90 },
    { h: 14.5, ml: 80 }, { h: 16.0, ml: 70 }, { h: 17.5, ml: 75 },
  ],
  "Missed morning, recovered": [
    { h: 8.0, ml: 60 }, { h: 10.0, ml: 80 }, { h: 12.5, ml: 200 },
    { h: 13.5, ml: 180 }, { h: 15.0, ml: 150 }, { h: 17.0, ml: 120 },
  ],
  "Barely drinking": [
    { h: 8.5, ml: 60 }, { h: 11.0, ml: 80 }, { h: 14.0, ml: 70 },
    { h: 17.0, ml: 60 },
  ],
  "Strong all day": [
    { h: 7.2, ml: 200 }, { h: 8.0, ml: 180 }, { h: 9.0, ml: 160 },
    { h: 10.0, ml: 150 }, { h: 11.0, ml: 140 }, { h: 12.5, ml: 120 },
    { h: 13.5, ml: 110 }, { h: 15.0, ml: 100 }, { h: 16.5, ml: 90 },
    { h: 18.0, ml: 80 },
  ],
  "Nothing so far": [],
};

// ── Pace model ──
function expectedIntake(h) {
  if (h < 7 || h > 21) return null; // night
  if (h <= 12) return 750 * (h - 7) / 5;
  return 750 + 750 * (h - 12) / 9;
}

function getPaceScore(events, simHour) {
  const cumulative = events
    .filter(e => e.h <= simHour)
    .reduce((s, e) => s + e.ml, 0);
  const target = expectedIntake(simHour);
  if (target === null || target === 0) return null;
  return Math.min(cumulative / target, 1.5);
}

function getStatus(score, lastDrinkMinsAgo, nightMode) {
  if (nightMode) return "NIGHT";
  if (score === null) return "NIGHT";
  if (score >= 0.8) return "GREEN";
  if (score >= 0.5) return "AMBER";
  return "RED";
}

function getCactus(score, lastDrinkMinsAgo, nightMode) {
  if (nightMode) return false;
  if (score === null) return false;
  return score < 0.5 && lastDrinkMinsAgo > 90;
}

function statusColor(status) {
  if (status === "GREEN") return GREEN;
  if (status === "AMBER") return AMBER;
  if (status === "RED") return RED;
  if (status === "NIGHT") return "#334155";
  return GREY;
}

function statusBg(status) {
  if (status === "GREEN") return "#F0FBF4";
  if (status === "AMBER") return "#FFF8E8";
  if (status === "RED") return "#FEF0EF";
  if (status === "NIGHT") return "#1E293B";
  return "#F5F5F5";
}

// ── Cactus SVG ──
function CactusSVG({ on, size = 80 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 100 100">
      {/* Pot */}
      <path d="M35,82 L38,95 L62,95 L65,82 Z" fill={on ? "#8B6914" : "#555"} />
      <rect x="30" y="78" width="40" height="6" rx="3" fill={on ? "#A0720F" : "#666"} />
      {/* Main stem */}
      <rect x="44" y="30" width="12" height="50" rx="6" fill={on ? "#2D8A4E" : "#444"} />
      {/* Left arm */}
      <rect x="26" y="46" width="20" height="10" rx="5" fill={on ? "#2D8A4E" : "#444"} />
      <rect x="24" y="36" width="10" height="22" rx="5" fill={on ? "#2D8A4E" : "#444"} />
      {/* Right arm */}
      <rect x="54" y="52" width="20" height="10" rx="5" fill={on ? "#2D8A4E" : "#444"} />
      <rect x="66" y="42" width="10" height="22" rx="5" fill={on ? "#2D8A4E" : "#444"} />
      {/* Spines */}
      {on && <>
        <line x1="50" y1="34" x2="50" y2="28" stroke="#A0C878" strokeWidth="1.5" />
        <line x1="44" y1="38" x2="38" y2="34" stroke="#A0C878" strokeWidth="1.5" />
        <line x1="56" y1="38" x2="62" y2="34" stroke="#A0C878" strokeWidth="1.5" />
        <line x1="50" y1="50" x2="50" y2="44" stroke="#A0C878" strokeWidth="1.5" />
        <line x1="28" y1="40" x2="24" y2="36" stroke="#A0C878" strokeWidth="1.5" />
        <line x1="68" y1="46" x2="72" y2="42" stroke="#A0C878" strokeWidth="1.5" />
      </>}
      {/* Glow when on */}
      {on && (
        <>
          <circle cx="50" cy="60" r="38" fill="#F4A261" opacity="0.12" />
          <circle cx="50" cy="60" r="28" fill="#F4A261" opacity="0.10" />
        </>
      )}
      {/* Face */}
      <circle cx="46" cy="52" r="2" fill={on ? "#1A5C32" : "#333"} />
      <circle cx="54" cy="52" r="2" fill={on ? "#1A5C32" : "#333"} />
      <path d={on ? "M45,58 Q50,63 55,58" : "M45,60 Q50,57 55,60"}
            fill="none" stroke={on ? "#1A5C32" : "#333"} strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

// ── Mini timeline bar ──
function Timeline({ events, simHour }) {
  const maxHour = 21;
  const minHour = 7;
  const range = maxHour - minHour;
  return (
    <div style={{ position: "relative", height: 20, background: "#E8EDF2", borderRadius: 4, overflow: "hidden" }}>
      {/* Current time marker */}
      <div style={{
        position: "absolute", left: `${Math.max(0, Math.min(100, (simHour - minHour) / range * 100))}%`,
        top: 0, width: 2, height: "100%", background: TEAL, zIndex: 2,
      }} />
      {/* 12pm marker */}
      <div style={{
        position: "absolute", left: `${(12 - minHour) / range * 100}%`,
        top: 0, width: 1, height: "100%", background: AMBER, opacity: 0.7,
      }} />
      {/* Drink events */}
      {events.map((e, i) => (
        <div key={i} style={{
          position: "absolute",
          left: `${(e.h - minHour) / range * 100}%`,
          top: 0, width: Math.max(3, e.ml / 20), height: "100%",
          background: TEAL, opacity: 0.7, borderRadius: 2,
        }} />
      ))}
    </div>
  );
}

export default function HydrationSimulator() {
  const [simHour, setSimHour] = useState(9);
  const [beds, setBeds] = useState(INITIAL_BEDS.map((b, i) => ({
    ...b,
    scenario: Object.keys(SCENARIOS)[i % Object.keys(SCENARIOS).length],
    events: Object.values(SCENARIOS)[i % Object.keys(SCENARIOS).length],
  })));
  const [selectedBed, setSelectedBed] = useState(null);
  const [view, setView] = useState("dashboard"); // "dashboard" | "cactus"
  const [nightMode, setNightMode] = useState(false);
  const [playing, setPlaying] = useState(false);
  const intervalRef = useRef(null);

  // Auto-play time
  useEffect(() => {
    if (playing) {
      intervalRef.current = setInterval(() => {
        setSimHour(h => {
          const next = parseFloat((h + 0.25).toFixed(2));
          if (next > 21) { setPlaying(false); return 21; }
          return next;
        });
      }, 400);
    } else {
      clearInterval(intervalRef.current);
    }
    return () => clearInterval(intervalRef.current);
  }, [playing]);

  // Night mode auto
  useEffect(() => {
    setNightMode(simHour < 7 || simHour > 22);
  }, [simHour]);

  function updateScenario(bedId, scenario) {
    setBeds(prev => prev.map(b => b.id === bedId
      ? { ...b, scenario, events: SCENARIOS[scenario] }
      : b
    ));
  }

  function addDrink(bedId, ml) {
    setBeds(prev => prev.map(b => b.id === bedId
      ? { ...b, events: [...b.events, { h: simHour, ml }].sort((a, c) => a.h - c.h) }
      : b
    ));
  }

  const formatHour = (h) => {
    const hour = Math.floor(h);
    const min = Math.round((h % 1) * 60);
    const ampm = hour >= 12 ? "pm" : "am";
    const displayHour = hour > 12 ? hour - 12 : hour === 0 ? 12 : hour;
    return `${displayHour}:${min.toString().padStart(2, "0")}${ampm}`;
  };

  const bedStats = beds.map(bed => {
    const score = getPaceScore(bed.events, simHour);
    const lastEvent = [...bed.events].filter(e => e.h <= simHour).sort((a, b) => b.h - a.h)[0];
    const lastDrinkMinsAgo = lastEvent ? Math.round((simHour - lastEvent.h) * 60) : 999;
    const cumulative = bed.events.filter(e => e.h <= simHour).reduce((s, e) => s + e.ml, 0);
    const status = getStatus(score, lastDrinkMinsAgo, nightMode);
    const cactusOn = getCactus(score, lastDrinkMinsAgo, nightMode);
    const target = expectedIntake(simHour);
    return { ...bed, score, status, cactusOn, cumulative, lastDrinkMinsAgo, target };
  });

  const redBeds = bedStats.filter(b => b.status === "RED");
  const amberBeds = bedStats.filter(b => b.status === "AMBER");
  const activeCactuses = bedStats.filter(b => b.cactusOn).length;

  return (
    <div style={{ fontFamily: "'Georgia', serif", background: CREAM, minHeight: "100vh", padding: 0 }}>

      {/* Header */}
      <div style={{ background: NAVY, padding: "14px 24px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div>
          <div style={{ color: MINT, fontSize: 11, letterSpacing: 3, fontFamily: "Calibri, sans-serif", fontWeight: "bold" }}>
            HYDRATION MONITORING SYSTEM
          </div>
          <div style={{ color: "white", fontSize: 20, fontWeight: "bold", marginTop: 2 }}>
            Ward Simulator
          </div>
        </div>
        <div style={{ display: "flex", gap: 10 }}>
          <button onClick={() => setView("dashboard")} style={{
            padding: "7px 18px", borderRadius: 6, border: "none", cursor: "pointer", fontFamily: "Calibri, sans-serif", fontWeight: "bold", fontSize: 12,
            background: view === "dashboard" ? TEAL : "transparent", color: view === "dashboard" ? "white" : MINT,
            outline: view !== "dashboard" ? `1px solid ${TEAL}` : "none",
          }}>📊 Dashboard</button>
          <button onClick={() => setView("cactus")} style={{
            padding: "7px 18px", borderRadius: 6, border: "none", cursor: "pointer", fontFamily: "Calibri, sans-serif", fontWeight: "bold", fontSize: 12,
            background: view === "cactus" ? TEAL : "transparent", color: view === "cactus" ? "white" : MINT,
            outline: view !== "cactus" ? `1px solid ${TEAL}` : "none",
          }}>🌵 Cactus View</button>
        </div>
      </div>

      {/* Time controls */}
      <div style={{ background: "white", borderBottom: `1px solid #E2E8EF`, padding: "12px 24px", display: "flex", alignItems: "center", gap: 20, flexWrap: "wrap" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ fontFamily: "Calibri, sans-serif", fontSize: 12, color: SLATE, fontWeight: "bold" }}>SIMULATED TIME</span>
          <span style={{ fontFamily: "Georgia", fontSize: 22, color: NAVY, fontWeight: "bold", minWidth: 80 }}>{formatHour(simHour)}</span>
        </div>
        <input type="range" min={7} max={21} step={0.25} value={simHour}
          onChange={e => setSimHour(parseFloat(e.target.value))}
          style={{ flex: 1, minWidth: 200, accentColor: TEAL }} />
        <button onClick={() => setPlaying(p => !p)} style={{
          padding: "7px 20px", borderRadius: 6, border: "none", cursor: "pointer",
          background: playing ? RED : SEAFOAM, color: "white", fontFamily: "Calibri, sans-serif", fontWeight: "bold", fontSize: 12,
        }}>
          {playing ? "⏸ Pause" : "▶ Play"}
        </button>
        {nightMode && (
          <div style={{ background: "#1E293B", color: "#94A3B8", padding: "5px 14px", borderRadius: 6, fontSize: 12, fontFamily: "Calibri, sans-serif" }}>
            🌙 Night Mode Active
          </div>
        )}
        {/* Summary pills */}
        <div style={{ display: "flex", gap: 8, marginLeft: "auto" }}>
          {[{ label: `${redBeds.length} RED`, bg: RED }, { label: `${amberBeds.length} AMBER`, bg: AMBER }, { label: `${activeCactuses} 🌵 ON`, bg: TEAL }].map(p => (
            <div key={p.label} style={{ background: p.bg, color: "white", padding: "4px 12px", borderRadius: 20, fontSize: 11, fontFamily: "Calibri, sans-serif", fontWeight: "bold" }}>
              {p.label}
            </div>
          ))}
        </div>
      </div>

      <div style={{ padding: 24 }}>

        {/* ── DASHBOARD VIEW ── */}
        {view === "dashboard" && (
          <div>
            <div style={{ marginBottom: 16, display: "flex", alignItems: "baseline", gap: 12 }}>
              <h2 style={{ margin: 0, color: NAVY, fontSize: 22 }}>Ward Heatmap</h2>
              <span style={{ fontFamily: "Calibri, sans-serif", fontSize: 12, color: SLATE }}>
                Tap a bed to inspect · Red beds shown first
              </span>
            </div>

            {/* Heatmap grid — red first */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 24 }}>
              {[...bedStats].sort((a, b) => {
                const order = { RED: 0, AMBER: 1, GREEN: 2, NIGHT: 3, GAP: 4 };
                return (order[a.status] ?? 5) - (order[b.status] ?? 5);
              }).map(bed => (
                <div key={bed.id} onClick={() => setSelectedBed(selectedBed?.id === bed.id ? null : bed)}
                  style={{
                    background: statusBg(bed.status), border: `2px solid ${statusColor(bed.status)}`,
                    borderRadius: 10, padding: "14px 16px", cursor: "pointer",
                    transition: "transform 0.15s, box-shadow 0.15s",
                    boxShadow: selectedBed?.id === bed.id ? `0 0 0 3px ${TEAL}` : "0 2px 8px rgba(0,0,0,0.07)",
                    transform: selectedBed?.id === bed.id ? "scale(1.02)" : "scale(1)",
                  }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                    <span style={{ fontFamily: "Calibri, sans-serif", fontWeight: "bold", fontSize: 13, color: NAVY }}>{bed.id}</span>
                    <div style={{ background: statusColor(bed.status), color: "white", fontSize: 9, fontWeight: "bold", padding: "2px 8px", borderRadius: 10, fontFamily: "Calibri, sans-serif" }}>
                      {bed.status}
                    </div>
                  </div>
                  <div style={{ fontFamily: "Calibri, sans-serif", fontSize: 10, color: SLATE, marginBottom: 6 }}>{bed.risk}</div>
                  <div style={{ fontFamily: "Georgia", fontSize: 20, fontWeight: "bold", color: statusColor(bed.status), marginBottom: 4 }}>
                    {bed.cumulative}ml
                  </div>
                  <div style={{ fontFamily: "Calibri, sans-serif", fontSize: 10, color: SLATE, marginBottom: 8 }}>
                    {bed.target ? `target: ${Math.round(bed.target)}ml` : "—"} · {bed.score !== null ? `${Math.round(bed.score * 100)}% pace` : "—"}
                  </div>
                  <Timeline events={bed.events} simHour={simHour} />
                  <div style={{ fontFamily: "Calibri, sans-serif", fontSize: 9, color: SLATE, marginTop: 4 }}>
                    Last drink: {bed.lastDrinkMinsAgo > 500 ? "none today" : `${bed.lastDrinkMinsAgo}m ago`}
                    {bed.cactusOn && <span style={{ marginLeft: 6, color: "#A0522D" }}>🌵 ON</span>}
                  </div>
                </div>
              ))}
            </div>

            {/* Selected bed detail */}
            {selectedBed && (() => {
              const bed = bedStats.find(b => b.id === selectedBed.id);
              if (!bed) return null;
              return (
                <div style={{ background: "white", border: `1px solid #E2E8EF`, borderRadius: 12, padding: 20, boxShadow: "0 2px 12px rgba(0,0,0,0.07)" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 16, flexWrap: "wrap", gap: 12 }}>
                    <div>
                      <div style={{ fontFamily: "Calibri, sans-serif", fontWeight: "bold", fontSize: 18, color: NAVY }}>{bed.id} — {bed.risk}</div>
                      <div style={{ fontFamily: "Calibri, sans-serif", fontSize: 12, color: SLATE, marginTop: 2 }}>
                        {bed.cumulative}ml consumed · {bed.target ? `${Math.round(bed.target)}ml expected by ${formatHour(simHour)}` : "Outside tracked hours"}
                      </div>
                    </div>
                    <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
                      <select value={bed.scenario} onChange={e => updateScenario(bed.id, e.target.value)}
                        style={{ padding: "5px 10px", borderRadius: 6, border: `1px solid #E2E8EF`, fontFamily: "Calibri, sans-serif", fontSize: 12, color: NAVY }}>
                        {Object.keys(SCENARIOS).map(s => <option key={s}>{s}</option>)}
                      </select>
                      <button onClick={() => addDrink(bed.id, 150)} style={{
                        padding: "6px 14px", borderRadius: 6, border: "none", background: TEAL, color: "white",
                        cursor: "pointer", fontFamily: "Calibri, sans-serif", fontSize: 12, fontWeight: "bold",
                      }}>+ 150ml drink</button>
                    </div>
                  </div>

                  {/* Event log */}
                  <div style={{ fontFamily: "Calibri, sans-serif", fontSize: 12, fontWeight: "bold", color: SLATE, marginBottom: 8 }}>DRINK LOG</div>
                  <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                    {bed.events.filter(e => e.h <= simHour).length === 0
                      ? <span style={{ color: SLATE, fontFamily: "Calibri, sans-serif", fontSize: 12 }}>No drinks recorded yet</span>
                      : bed.events.filter(e => e.h <= simHour).map((e, i) => (
                        <div key={i} style={{ background: MINT, border: `1px solid ${TEAL}`, borderRadius: 6, padding: "4px 10px", fontSize: 11, fontFamily: "Calibri, sans-serif", color: NAVY }}>
                          {formatHour(e.h)} — {e.ml}ml
                        </div>
                      ))
                    }
                  </div>
                </div>
              );
            })()}
          </div>
        )}

        {/* ── CACTUS VIEW ── */}
        {view === "cactus" && (
          <div>
            <div style={{ marginBottom: 16, display: "flex", alignItems: "baseline", gap: 12 }}>
              <h2 style={{ margin: 0, color: NAVY, fontSize: 22 }}>Bedside Cactus States</h2>
              <span style={{ fontFamily: "Calibri, sans-serif", fontSize: 12, color: SLATE }}>
                Lit = patient should drink now · Dark = no action needed
              </span>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16 }}>
              {bedStats.map(bed => (
                <div key={bed.id} style={{
                  background: bed.cactusOn ? "#FFF8F0" : "white",
                  border: `2px solid ${bed.cactusOn ? "#F4A261" : "#E2E8EF"}`,
                  borderRadius: 12, padding: 20, textAlign: "center",
                  boxShadow: bed.cactusOn ? "0 0 20px rgba(244,162,97,0.25)" : "0 2px 8px rgba(0,0,0,0.05)",
                  transition: "all 0.3s",
                }}>
                  <div style={{ fontFamily: "Calibri, sans-serif", fontWeight: "bold", fontSize: 13, color: NAVY, marginBottom: 4 }}>{bed.id}</div>
                  <div style={{ fontFamily: "Calibri, sans-serif", fontSize: 10, color: SLATE, marginBottom: 12 }}>{bed.risk}</div>

                  <div style={{ display: "flex", justifyContent: "center", marginBottom: 12 }}>
                    <CactusSVG on={bed.cactusOn} size={75} />
                  </div>

                  <div style={{
                    fontFamily: "Calibri, sans-serif", fontSize: 11, fontWeight: "bold",
                    color: bed.cactusOn ? "#A0522D" : (nightMode ? "#64748B" : TEAL),
                    marginBottom: 8,
                  }}>
                    {nightMode ? "🌙 NIGHT MODE" : bed.cactusOn ? "💧 DRINK NOW" : "✓ OK"}
                  </div>

                  <div style={{ fontFamily: "Calibri, sans-serif", fontSize: 10, color: SLATE }}>
                    {bed.cumulative}ml · {bed.score !== null ? `${Math.round(bed.score * 100)}% pace` : "—"}
                  </div>
                  <div style={{ fontFamily: "Calibri, sans-serif", fontSize: 10, color: SLATE, marginTop: 2 }}>
                    Last: {bed.lastDrinkMinsAgo > 500 ? "none today" : `${bed.lastDrinkMinsAgo}m ago`}
                  </div>

                  {/* Reason why cactus is on */}
                  {bed.cactusOn && (
                    <div style={{ marginTop: 10, background: "#FFF0E0", border: "1px solid #F4A261", borderRadius: 6, padding: "5px 8px", fontSize: 10, fontFamily: "Calibri, sans-serif", color: "#8B4513" }}>
                      {bed.score < 0.5 ? `${Math.round((1 - bed.score) * 100)}% below pace` : ""}{bed.lastDrinkMinsAgo > 90 ? ` · ${bed.lastDrinkMinsAgo}m since last drink` : ""}
                    </div>
                  )}

                  {/* Quick drink button */}
                  <button onClick={() => addDrink(bed.id, 150)} style={{
                    marginTop: 10, padding: "5px 14px", borderRadius: 6, border: "none",
                    background: bed.cactusOn ? TEAL : "#E2E8EF", color: bed.cactusOn ? "white" : SLATE,
                    cursor: "pointer", fontFamily: "Calibri, sans-serif", fontSize: 11, fontWeight: "bold", width: "100%",
                  }}>+ 150ml drink</button>
                </div>
              ))}
            </div>

            {/* Logic explanation */}
            <div style={{ marginTop: 24, background: MINT, border: `1px solid ${TEAL}`, borderRadius: 10, padding: "14px 20px" }}>
              <div style={{ fontFamily: "Calibri, sans-serif", fontWeight: "bold", color: NAVY, fontSize: 12, marginBottom: 6 }}>CACTUS LOGIC AT {formatHour(simHour)}</div>
              <div style={{ fontFamily: "Calibri, sans-serif", fontSize: 11, color: SLATE, lineHeight: 1.7 }}>
                Cactus turns <strong>ON</strong> when: pace score &lt; 50% AND last drink &gt; 90 minutes ago AND not in night mode (10pm–7am).
                &nbsp;·&nbsp; Turns <strong>OFF</strong> immediately when a drink event is recorded.
                &nbsp;·&nbsp; Currently: <strong>{activeCactuses} of {beds.length} cactuses lit</strong>.
                &nbsp;·&nbsp; Expected intake at {formatHour(simHour)}: <strong>{Math.round(expectedIntake(simHour) || 0)}ml</strong> (50% of daily 1500ml target must be reached by 12pm).
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
