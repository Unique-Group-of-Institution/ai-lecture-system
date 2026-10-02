import React from 'react';
import {
  AbsoluteFill,
  Audio,
  interpolate,
  Sequence,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import {TransitionSeries, linearTiming} from '@remotion/transitions';
import {fade} from '@remotion/transitions/fade';
import {slide} from '@remotion/transitions/slide';
import {BackgroundWaves} from '../ch12/visuals';
import scenesData from '../../lecture1-scenes.json';
import audioData from '../../lecture1-audio.json';

export const FPS = 30;
const TRANSITION = 15;
const GAP = 12;
const TAIL = 45;

const CYAN = '#22d3ee';
const ORANGE = '#fb923c';
const GOLD = '#fbbf24';
const GREEN = '#22c55e';

type Segment = {voice: string; text: string};
type Scene = {
  id: number;
  kind: string;
  title: string;
  subtitle?: string;
  visual?: string;
  accent?: string;
  segments: Segment[];
  bullets?: string[];
  answers?: string[];
  terms?: {en: string; ur: string}[];
  termBatches?: number[];
  questions?: {q: string; options: string[]; answer: number}[];
};
type AudioEntry = {file: string; voice: string; durationMs: number};

const scenes = scenesData.scenes as Scene[];
const audio = audioData as Record<string, AudioEntry[]>;
const config = scenesData.config as {fontFamily: string; urduFontFamily: string; fontScale: number};

const framesOf = (ms: number) => Math.round((ms * FPS) / 1000);

const sceneEntries = (s: Scene) => audio[String(s.id)];

export const sceneFrames = (s: Scene) => {
  const segs = sceneEntries(s);
  const sum = segs.reduce((acc, e) => acc + framesOf(e.durationMs) + GAP, 0);
  return sum + TAIL;
};

export const totalFrames = () =>
  scenes.reduce((acc, s) => acc + sceneFrames(s), 0) - TRANSITION * (scenes.length - 1);

export type Lecture1Config = {
  fontFamily: string;
  urduFontFamily: string;
  fontScale: number;
};

export const defaultConfig: Lecture1Config = {
  fontFamily: config.fontFamily,
  urduFontFamily: config.urduFontFamily,
  fontScale: config.fontScale,
};

const appear = (frame: number, from: number) =>
  spring({frame: frame - from, fps: FPS, config: {damping: 18, stiffness: 120}});

const Ctx = React.createContext<Lecture1Config & {scene: Scene; sceneStart: number}>({
  ...defaultConfig,
  scene: scenes[0],
  sceneStart: 0,
});

const useCfg = () => React.useContext(Ctx);

const Shell: React.FC<{children: React.ReactNode}> = ({children}) => {
  const {fontFamily} = useCfg();
  return (
    <AbsoluteFill
      style={{
        background:
          'radial-gradient(1200px 800px at 20% 10%, #0b1a5e 0%, #060d33 55%, #04081f 100%)',
        fontFamily,
        color: '#e2e8f0',
      }}
    >
      {children}
    </AbsoluteFill>
  );
};

const Header: React.FC<{index: number}> = ({index}) => {
  const {fontScale} = useCfg();
  return (
    <div style={{display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '24px 60px 0'}}>
      <div style={{display: 'flex', alignItems: 'center', gap: 22}}>
        <img src={staticFile('branding/logo.png')} style={{height: 88, borderRadius: '50%'}} alt="UGI" />
        <div>
          <div style={{fontSize: 27 * fontScale, fontWeight: 800, color: '#ffffff', letterSpacing: 1}}>
            UNIQUE GROUP OF INSTITUTIONS · LAHORE
          </div>
          <div style={{fontSize: 23 * fontScale, color: '#7dd3fc', marginTop: 4, fontWeight: 700}}>
            CHEMISTRY · CLASS 9 · UNIT 1 · LECTURE 1
          </div>
        </div>
      </div>
      <div style={{fontSize: 24, color: '#94a3b8'}}>
        {String(index).padStart(2, '0')} / {String(scenes.length).padStart(2, '0')}
      </div>
    </div>
  );
};

const GlobalProgress: React.FC = () => {
  const frame = useCurrentFrame();
  const {sceneStart} = useCfg();
  const {durationInFrames} = useVideoConfig();
  const p = interpolate(sceneStart + frame, [0, durationInFrames], [0, 1], {extrapolateRight: 'clamp'});
  return (
    <div style={{position: 'absolute', left: 0, bottom: 0, width: '100%', height: 8, background: 'rgba(148,163,184,0.2)'}}>
      <div style={{width: `${p * 100}%`, height: '100%', background: `linear-gradient(90deg, ${CYAN}, ${GOLD})`}} />
    </div>
  );
};

const Title: React.FC<{children: React.ReactNode; start?: number}> = ({children, start = 6}) => {
  const frame = useCurrentFrame();
  const {fontScale} = useCfg();
  const p = appear(frame, start);
  return (
    <div style={{padding: '18px 60px 0', opacity: p, transform: `translateY(${(1 - p) * 30}px)`}}>
      <h2 style={{fontSize: 54 * fontScale, margin: 0, color: GOLD, fontWeight: 900, lineHeight: 1.2}}>{children}</h2>
    </div>
  );
};

const useSegWindows = () => {
  const {scene} = useCfg();
  const segs = sceneEntries(scene);
  const windows: {voice: string; start: number; end: number; i: number}[] = [];
  let t = 0;
  for (const e of segs) {
    const d = framesOf(e.durationMs);
    windows.push({voice: e.voice, start: t, end: t + d, i: windows.length});
    t += d + GAP;
  }
  return windows;
};

const Bullets: React.FC<{until: number}> = ({until}) => {
  const frame = useCurrentFrame();
  const {scene, fontScale} = useCfg();
  const bullets = scene.bullets ?? [];
  const windows = useSegWindows();
  const enWindows = windows.filter((w) => w.voice === 'en' && w.end <= until + 10);
  const spanStart = enWindows.length ? enWindows[0].start : 0;
  const spanEnd = enWindows.length ? enWindows[enWindows.length - 1].end : until;
  const step = Math.max(18, Math.floor((spanEnd - spanStart) / Math.max(1, bullets.length)));
  return (
    <div>
      {bullets.map((b, i) => {
        const p = appear(frame, spanStart + 15 + i * step);
        return (
          <div
            key={i}
            style={{
              opacity: p,
              transform: `translateX(${(1 - p) * 60}px)`,
              display: 'flex',
              alignItems: 'flex-start',
              gap: 16,
              fontSize: 30 * fontScale,
              lineHeight: 1.35,
              marginBottom: 16,
              background: 'rgba(13,26,84,0.55)',
              border: '1px solid rgba(56,189,248,0.25)',
              borderRadius: 14,
              padding: '14px 22px',
            }}
          >
            <span style={{color: CYAN, fontWeight: 900}}>▸</span>
            <span>{b}</span>
          </div>
        );
      })}
    </div>
  );
};

const UrduPanel: React.FC = () => {
  const frame = useCurrentFrame();
  const {scene, urduFontFamily, fontScale} = useCfg();
  const windows = useSegWindows();
  const urWins = windows.filter((w) => w.voice === 'ur');
  const active = urWins.find((w) => frame >= w.start - 5 && frame <= w.end + TAIL);
  if (!active) return null;
  const p = appear(frame, active.start - 5);
  const out = interpolate(frame, [active.end + TAIL - 15, active.end + TAIL], [1, 0], {extrapolateLeft: 'clamp'});
  const text = scene.segments[active.i]?.text ?? '';
  return (
    <div
      style={{
        position: 'absolute',
        left: 60,
        right: 60,
        bottom: 26,
        opacity: p * out,
        transform: `translateY(${(1 - p) * 40}px)`,
        direction: 'rtl',
        textAlign: 'right',
        fontFamily: urduFontFamily,
        fontSize: 33 * fontScale,
        lineHeight: 1.9,
        color: '#f1f5f9',
        background: 'linear-gradient(90deg, rgba(251,191,36,0.16), rgba(13,26,84,0.75))',
        borderRight: `6px solid ${GOLD}`,
        borderRadius: 14,
        padding: '10px 26px',
      }}
    >
      {text}
    </div>
  );
};

/* ---------------- visuals ---------------- */

const Atom: React.FC<{size?: number}> = ({size = 560}) => {
  const frame = useCurrentFrame();
  const p = appear(frame, 8);
  const spin = frame * 0.045;
  const r = size / 2;
  const orbits = [
    {tilt: 0, color: CYAN, phase: 0},
    {tilt: 60, color: ORANGE, phase: 2.1},
    {tilt: 120, color: GREEN, phase: 4.2},
  ];
  return (
    <svg width={size} height={size} style={{opacity: p, transform: `scale(${0.7 + 0.3 * p})`}}>
      <g transform={`translate(${r},${r})`}>
        {orbits.map((o, i) => (
          <g key={i} transform={`rotate(${o.tilt})`}>
            <ellipse rx={r * 0.86} ry={r * 0.32} fill="none" stroke={o.color} strokeWidth={3} opacity={0.5} />
            <circle cx={r * 0.86 * Math.cos(spin * (1 + i * 0.15) + o.phase)} cy={r * 0.32 * Math.sin(spin * (1 + i * 0.15) + o.phase)} r={13} fill={o.color} />
          </g>
        ))}
        <circle r={48 + 4 * Math.sin(frame * 0.12)} fill={GOLD} opacity={0.95} />
        <circle r={74} fill={GOLD} opacity={0.14} />
        <text y={10} textAnchor="middle" fontSize={28} fontWeight={900} fill="#081033">MATTER</text>
      </g>
    </svg>
  );
};

const BranchIcon: React.FC<{kind: string; color: string; size?: number}> = ({kind, color, size = 300}) => {
  const frame = useCurrentFrame();
  const p = appear(frame, 14);
  const t = frame * 0.05;
  const s = size;
  const c = s / 2;
  const common = {stroke: color, fill: 'none', strokeWidth: 5} as const;
  let inner: React.ReactNode = null;
  if (kind === 'physical')
    inner = (
      <g>
        <circle cx={c} cy={c} r={s * 0.12} fill={color} />
        {[0, 60, 120].map((a) => (
          <g key={a} transform={`rotate(${a} ${c} ${c})`}>
            <ellipse cx={c} cy={c} rx={s * 0.4} ry={s * 0.16} {...common} opacity={0.7} />
            <circle cx={c + s * 0.4 * Math.cos(t + a)} cy={c + s * 0.16 * Math.sin(t + a)} r={10} fill={color} />
          </g>
        ))}
      </g>
    );
  else if (kind === 'inorganic')
    inner = (
      <g>
        <path d={`M${c - 60},${c - 70} v90 a60 60 0 0 0 120 0 v-90 h-38 v90 a22 22 0 0 1 -44 0 v-90 z`} {...common} />
        <rect x={c - 60} y={c - 92} width={44} height={24} fill="#ef4444" />
        <rect x={c + 16} y={c - 92} width={44} height={24} fill="#334155" />
      </g>
    );
  else if (kind === 'organic')
    inner = (
      <g>
        <polygon
          points={Array.from({length: 6}, (_, i) => {
            const a = (Math.PI / 3) * i - Math.PI / 6;
            return `${c + s * 0.34 * Math.cos(a)},${c + s * 0.34 * Math.sin(a)}`;
          }).join(' ')}
          {...common}
        />
        <circle cx={c} cy={c} r={s * 0.2} stroke={color} fill="none" strokeWidth={4} opacity={0.5 + 0.3 * Math.sin(t * 2)} />
      </g>
    );
  else if (kind === 'environmental')
    inner = (
      <g>
        <circle cx={c} cy={c} r={s * 0.32} {...common} />
        <path d={`M${c - s * 0.32},${c} a 32 14 0 0 0 ${s * 0.64} 0`} stroke={color} fill="none" strokeWidth={3} opacity={0.6} />
        <path d={`M${c + s * 0.36},${c - s * 0.3} q 26 10 26 34 q -26 -6 -26 -34 z`} fill={GREEN} opacity={0.9} />
      </g>
    );
  else if (kind === 'analytical')
    inner = (
      <g>
        <path d={`M${c - 18},${c - 80} h36 v46 l52 84 a14 14 0 0 1 -12 22 h-116 a14 14 0 0 1 -12 -22 l52 -84 z`} {...common} />
        <path d={`M${c - 44},${c + 40} h88 l18 30 h-124 z`} fill={color} opacity={0.5} />
        {[0, 1, 2].map((i) => (
          <circle key={i} cx={c - 20 + i * 22} cy={c + 58 - ((frame * 2 + i * 30) % 46)} r={6} fill="#fff" opacity={0.8} />
        ))}
      </g>
    );
  else if (kind === 'bio')
    inner = (
      <g>
        {[-1, 1].map((side) => (
          <path
            key={side}
            d={Array.from({length: 24}, (_, i) => {
              const y = c - 90 + i * 8;
              const x = c + side * 46 * Math.sin(i * 0.55 + t);
              return `${i === 0 ? 'M' : 'L'}${x},${y}`;
            }).join(' ')}
            stroke={side === -1 ? color : GOLD}
            fill="none"
            strokeWidth={6}
          />
        ))}
        {Array.from({length: 6}, (_, i) => {
          const y = c - 70 + i * 30;
          const x1 = c + 46 * Math.sin((i * 3.75) * 0.55 + t);
          return <line key={i} x1={c - x1} x2={c + x1} y1={y} y2={y} stroke="#94a3b8" strokeWidth={4} opacity={0.7} />;
        })}
      </g>
    );
  else if (kind === 'nuclear')
    inner = (
      <g>
        {[-1, 0, 1].map((r1) =>
          [-1, 0, 1].map((r2) => (
            <circle key={`${r1}${r2}`} cx={c + r1 * 22} cy={c + r2 * 22} r={11} fill={(r1 + r2) % 2 === 0 ? color : GOLD} opacity={0.9} />
          )),
        )}
        {[0, 120, 240].map((a) => (
          <path key={a} d={`M${c},${c} l${70 * Math.cos(((a + frame * 3) * Math.PI) / 180)},${70 * Math.sin(((a + frame * 3) * Math.PI) / 180)}`} stroke={color} strokeWidth={6} strokeLinecap="round" />
        ))}
      </g>
    );
  else if (kind === 'polymer')
    inner = (
      <g>
        {Array.from({length: 5}, (_, i) => {
          const x = c - 96 + i * 48;
          const y = c + 26 * Math.sin(t + i * 0.9);
          return (
            <g key={i}>
              {i < 4 ? <line x1={x + 18} y1={y} x2={x + 30} y2={c + 26 * Math.sin(t + (i + 1) * 0.9)} stroke="#94a3b8" strokeWidth={6} /> : null}
              <circle cx={x} cy={y} r={18} fill={i % 2 ? GOLD : color} opacity={0.9} />
            </g>
          );
        })}
      </g>
    );
  else if (kind === 'geo')
    inner = (
      <g>
        <path d={`M${c - 110},${c + 70} L${c - 30},${c - 70} L${c + 20},${c + 10} L${c + 70},${c - 40} L${c + 120},${c + 70} Z`} {...common} />
        <path d={`M${c - 110},${c + 70} h230`} stroke={color} strokeWidth={5} />
        <circle cx={c + 60} cy={c + 40} r={7} fill={GOLD} opacity={0.6 + 0.4 * Math.sin(t * 3)} />
        <circle cx={c - 20} cy={c + 50} r={7} fill={GOLD} opacity={0.6 + 0.4 * Math.sin(t * 3 + 2)} />
      </g>
    );
  else if (kind === 'medicinal')
    inner = (
      <g transform={`rotate(${18 * Math.sin(t)} ${c} ${c})`}>
        <rect x={c - 80} y={c - 30} width={80} height={60} rx={30} fill={color} />
        <rect x={c} y={c - 30} width={80} height={60} rx={30} fill="#f8fafc" />
        <line x1={c} y1={c - 30} x2={c} y2={c + 30} stroke="#0b1a5e" strokeWidth={3} />
      </g>
    );
  else if (kind === 'astro')
    inner = (
      <g>
        <circle cx={c} cy={c} r={s * 0.22} fill={color} opacity={0.9} />
        <ellipse cx={c} cy={c} rx={s * 0.42} ry={s * 0.12} fill="none" stroke={GOLD} strokeWidth={5} transform={`rotate(-18 ${c} ${c})`} />
        {[40, 130, 220, 310].map((a) => (
          <circle key={a} cx={c + (s * 0.44) * Math.cos(((a + frame) * Math.PI) / 180)} cy={c + (s * 0.16) * Math.sin(((a + frame) * Math.PI) / 180)} r={4} fill="#fff" opacity={0.8} />
        ))}
      </g>
    );
  else if (kind === 'daily') {
    const spots = [-150, -75, 0, 75, 150];
    const labels = ['KITCHEN', 'CLEAN', 'HEALTH', 'FARM', 'FACTORY'];
    inner = (
      <g>
        {spots.map((dx, i) => {
          const ip = appear(frame, 25 + i * 45);
          const x = c + dx;
          const y = c - 20;
          const b = {stroke: color, fill: 'none', strokeWidth: 4} as const;
          return (
            <g key={i} opacity={ip} transform={`translate(${x},${y}) scale(${0.5 + 0.5 * ip})`}>
              {i === 0 ? (
                <g>
                  <rect x={-22} y={-8} width={44} height={26} rx={6} {...b} />
                  <line x1={-28} y1={-8} x2={28} y2={-8} stroke={color} strokeWidth={5} />
                  <path d="M0,-26 q8,-8 0,-16 q -8,8 0,16 z" fill={ORANGE} opacity={0.9} />
                </g>
              ) : null}
              {i === 1 ? (
                <g>
                  <rect x={-16} y={-6} width={32} height={24} rx={8} {...b} />
                  <circle cx={-8} cy={-18} r={6} fill={CYAN} opacity={0.8} />
                  <circle cx={6} cy={-24} r={4} fill={CYAN} opacity={0.6} />
                  <circle cx={14} cy={-14} r={3} fill={CYAN} opacity={0.7} />
                </g>
              ) : null}
              {i === 2 ? (
                <g transform="rotate(-20)">
                  <rect x={-20} y={-9} width={20} height={18} rx={9} fill={color} />
                  <rect x={0} y={-9} width={20} height={18} rx={9} fill="#f8fafc" />
                </g>
              ) : null}
              {i === 3 ? (
                <g>
                  <path d={`M0,20 C0,0 0,0 0,-4`} stroke={GREEN} strokeWidth={5} fill="none" />
                  <path d="M0,-4 q-18,-4 -20,-20 q18,2 20,20 z" fill={GREEN} opacity={0.9} />
                  <path d={`M0,4 q18,-4 20,-20 q-18,2 -20,20 z`} fill={GREEN} opacity={0.7} transform="scale(-1,1) translate(2,0)" />
                  <line x1={-16} y1={20} x2={16} y2={20} stroke={color} strokeWidth={4} />
                </g>
              ) : null}
              {i === 4 ? (
                <g>
                  <path d="M-22,20 v-20 l12,-8 v8 l12,-8 v8 l12,-8 v28 z" {...b} />
                  <rect x={14} y={-24} width={8} height={14} {...b} />
                  <circle cx={18} cy={-32 - (frame % 30) / 4} r={4} fill="#94a3b8" opacity={0.7} />
                </g>
              ) : null}
              <text y={56} textAnchor="middle" fontSize={16} fontWeight={900} fill={color} letterSpacing={0.5}>
                {labels[i]}
              </text>
            </g>
          );
        })}
      </g>
    );
  } else if (kind === 'states')
    inner = (
      <g>
        {Array.from({length: 9}, (_, i) => (
          <circle key={i} cx={c - 100 + (i % 3) * 26} cy={c - 26 + Math.floor(i / 3) * 26} r={10} fill={CYAN} />
        ))}
        {Array.from({length: 6}, (_, i) => (
          <circle key={`l${i}`} cx={c - 10 + ((i * 37 + frame) % 90)} cy={c + 30 + 14 * Math.sin(i + t * 2)} r={10} fill={GOLD} />
        ))}
        {Array.from({length: 6}, (_, i) => (
          <circle key={`g${i}`} cx={c + 20 + ((i * 53 + frame * 2) % 110)} cy={c - 60 + ((i * 71 + frame) % 120)} r={7} fill="#94a3b8" opacity={0.8} />
        ))}
      </g>
    );
  return <svg width={s} height={s} style={{opacity: p}}>{inner}</svg>;
};

const BRANCHES11 = [
  {label: 'Physical', color: CYAN},
  {label: 'Inorganic', color: ORANGE},
  {label: 'Organic', color: GREEN},
  {label: 'Environmental', color: '#38bdf8'},
  {label: 'Analytical', color: GOLD},
  {label: 'Biochemistry', color: '#a78bfa'},
  {label: 'Nuclear', color: '#f472b6'},
  {label: 'Polymer', color: '#4ade80'},
  {label: 'Geochemistry', color: '#f59e0b'},
  {label: 'Medicinal', color: '#06b6d4'},
  {label: 'Astrochemistry', color: '#818cf8'},
];

const HexagonMap: React.FC<{frames: number}> = ({frames}) => {
  const frame = useCurrentFrame();
  const {fontScale, scene} = useCfg();
  const cx = 860;
  const cy = 340;
  const core = appear(frame, 10);
  const windows = useSegWindows();
  const en = windows.find((w) => w.voice === 'en');
  const urStart = windows.find((w) => w.voice === 'ur')?.start ?? frames;
  const step = (urStart - 20 - (en?.start ?? 0)) / BRANCHES11.length;
  return (
    <svg width={1720} height={640}>
      {BRANCHES11.map((b, i) => {
        const ang = (Math.PI * 2 * i) / BRANCHES11.length - Math.PI / 2;
        const nx = cx + 640 * Math.cos(ang);
        const ny = cy + 260 * Math.sin(ang);
        const start = (en?.start ?? 0) + 20 + i * step;
        const p = appear(frame, start);
        const line = p;
        const firstWord = scene.title.split(' ')[0].toLowerCase();
        const active = scene.kind === 'branch' && b.label.toLowerCase() === firstWord;
        return (
          <g key={b.label}>
            <line x1={cx} y1={cy} x2={cx + (nx - cx) * line} y2={cy + (ny - cy) * line} stroke={b.color} strokeWidth={4} opacity={0.7} />
            <g opacity={p} transform={`translate(${nx},${ny}) scale(${active ? 1.15 : 0.6 + 0.4 * p})`}>
              <rect x={-150} y={-30} width={300} height={60} rx={18} fill="rgba(8,15,55,0.85)" stroke={b.color} strokeWidth={active ? 5 : 3} />
              <text y={10} textAnchor="middle" fontSize={28 * fontScale} fontWeight={900} fill={b.color}>
                {b.label}
              </text>
            </g>
          </g>
        );
      })}
      <g opacity={core} transform={`translate(${cx},${cy}) scale(${0.6 + 0.4 * core})`}>
        <polygon
          points={Array.from({length: 6}, (_, i) => {
            const a = (Math.PI * 2 * i) / 6 - Math.PI / 6;
            return `${180 * Math.cos(a)},${180 * Math.sin(a)}`;
          }).join(' ')}
          fill="rgba(19,32,96,0.92)"
          stroke={GOLD}
          strokeWidth={5}
        />
        <text y={12} textAnchor="middle" fontSize={44} fontWeight={900} fill={GOLD}>
          CHEMISTRY
        </text>
      </g>
    </svg>
  );
};

const DefinitionExtras: React.FC = () => {
  const frame = useCurrentFrame();
  const {fontScale} = useCfg();
  return (
    <div style={{marginTop: 6}}>
      <div style={{display: 'flex', gap: 14, flexWrap: 'wrap', opacity: appear(frame, 40)}}>
        {[
          ['PROPERTIES', CYAN],
          ['COMPOSITION', GOLD],
          ['STRUCTURE', GREEN],
        ].map(([txt, col]) => (
          <span key={txt} style={{background: col as string, color: '#081033', fontWeight: 900, fontSize: 27 * fontScale, padding: '7px 20px', borderRadius: 999}}>
            {txt}
          </span>
        ))}
        <span style={{fontSize: 25 * fontScale, color: '#94a3b8', alignSelf: 'center'}}>of substances</span>
      </div>
    </div>
  );
};

const ExerciseVisual: React.FC<{frames: number}> = ({frames}) => {
  const frame = useCurrentFrame();
  const {scene, fontScale} = useCfg();
  const answers = scene.answers ?? [];
  const windows = useSegWindows();
  const ur = windows.find((w) => w.voice === 'ur');
  const revealStart = ur ? ur.start + 60 : frames - 180;
  return (
    <div style={{display: 'flex', flexDirection: 'column', gap: 18, paddingTop: 10}}>
      {(scene.bullets ?? []).map((q, i) => {
        const p = appear(frame, 30 + i * 40);
        const ap = appear(frame, revealStart + i * 55);
        return (
          <div key={i} style={{opacity: p, display: 'flex', alignItems: 'center', gap: 20, fontSize: 30 * fontScale}}>
            <div style={{flex: '0 0 55%', background: 'rgba(13,26,84,0.55)', border: '1px solid rgba(56,189,248,0.25)', borderRadius: 14, padding: '16px 22px'}}>
              {q}
            </div>
            <div style={{color: '#64748b', fontSize: 34 * fontScale}}>→</div>
            <div
              style={{
                opacity: ap,
                transform: `scale(${0.6 + 0.4 * ap})`,
                background: `linear-gradient(135deg, ${GOLD}, ${ORANGE})`,
                color: '#1a1206',
                fontWeight: 900,
                fontSize: 28 * fontScale,
                padding: '12px 26px',
                borderRadius: 999,
              }}
            >
              {answers[i]}
            </div>
          </div>
        );
      })}
    </div>
  );
};

/* ---------------- scenes ---------------- */

const GlossaryVisual: React.FC<{frames: number}> = ({frames}) => {
  const frame = useCurrentFrame();
  const {scene, urduFontFamily, fontScale} = useCfg();
  const terms = scene.terms ?? [];
  const batches = scene.termBatches ?? [];
  const windows = useSegWindows();
  const enWindows = windows.filter((w) => w.voice === 'en');
  let idx = 0;
  const anchors: number[] = terms.map((_, i) => {
    while (idx < batches.length - 1 && i >= batches.slice(0, idx + 1).reduce((a, b) => a + b, 0)) idx++;
    return (enWindows[idx + 1]?.start ?? 30) + 10;
  });
  const urActive = windows.find((w) => w.voice === 'ur' && frame >= w.start - 5 && frame <= w.end + 20);
  return (
    <div style={{display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 18, paddingTop: 14, width: '100%'}}>
      {terms.map((t, i) => {
        const p = appear(frame, anchors[i]);
        const showUr = !!urActive && frame >= anchors[i];
        return (
          <div
            key={t.en}
            style={{
              opacity: p,
              transform: `translateY(${(1 - p) * 36}px) scale(${0.7 + 0.3 * p})`,
              background: 'rgba(13,26,84,0.6)',
              border: `1px solid ${showUr ? GOLD : 'rgba(56,189,248,0.25)'}`,
              boxShadow: showUr ? `0 0 22px rgba(251,191,36,0.35)` : 'none',
              borderRadius: 16,
              padding: '16px 20px',
              textAlign: 'center',
            }}
          >
            <div style={{fontSize: 32 * fontScale, fontWeight: 900, color: CYAN}}>{t.en}</div>
            <div style={{fontSize: 28 * fontScale, marginTop: 6, opacity: showUr ? 1 : 0.25, fontFamily: urduFontFamily, direction: 'rtl', color: '#f1f5f9', transition: 'opacity 0.2s'}}>
              {t.ur}
            </div>
          </div>
        );
      })}
    </div>
  );
};

const McqVisual: React.FC<{frames: number}> = ({frames}) => {
  const frame = useCurrentFrame();
  const {scene, fontScale} = useCfg();
  const questions = scene.questions ?? [];
  const windows = useSegWindows();
  const en = windows.filter((w) => w.voice === 'en');
  const ur = windows.filter((w) => w.voice === 'ur');
  let qi = 0;
  for (let i = 1; i < en.length; i++) if (frame >= en[i].start - 8) qi = i - 1;
  const q = questions[qi];
  if (!q) return null;
  const answerAt = (ur[qi + 1]?.start ?? frames - 120) + Math.min(90, framesOf(2500));
  const qp = appear(frame, Math.max(10, (en[qi + 1]?.start ?? 10) - 8));
  return (
    <div style={{paddingTop: 10, width: '100%', opacity: qp, transform: `translateY(${(1 - qp) * 30}px)`}}>
      <div style={{display: 'flex', gap: 18, alignItems: 'flex-start', marginBottom: 26}}>
        <div style={{flex: '0 0 auto', background: GOLD, color: '#1a1206', fontWeight: 900, fontSize: 30 * fontScale, borderRadius: 12, padding: '8px 18px'}}>
          Q{qi + 1}
        </div>
        <div style={{fontSize: 36 * fontScale, fontWeight: 800, color: '#f1f5f9', lineHeight: 1.35}}>{q.q}</div>
      </div>
      <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 18}}>
        {q.options.map((opt, i) => {
          const op = appear(frame, 26 + qi * 10 + i * 10);
          const correct = i === q.answer;
          const revealed = frame >= answerAt;
          return (
            <div
              key={i}
              style={{
                opacity: op,
                transform: `translateX(${(1 - op) * 40}px)`,
                display: 'flex',
                alignItems: 'center',
                gap: 16,
                fontSize: 29 * fontScale,
                background: revealed && correct ? 'rgba(34,197,94,0.22)' : 'rgba(13,26,84,0.55)',
                border: `1px solid ${revealed && correct ? GREEN : 'rgba(56,189,248,0.25)'}`,
                boxShadow: revealed && correct ? '0 0 26px rgba(34,197,94,0.4)' : 'none',
                borderRadius: 14,
                padding: '14px 22px',
              }}
            >
              <span style={{fontWeight: 900, color: revealed && correct ? GREEN : CYAN}}>{String.fromCharCode(65 + i)}.</span>
              <span style={{flex: 1}}>{opt}</span>
              {revealed && correct ? <span style={{color: GREEN, fontWeight: 900, fontSize: 32}}>✓</span> : null}
            </div>
          );
        })}
      </div>
    </div>
  );
};

const TitleScene: React.FC = () => {
  const frame = useCurrentFrame();
  const {fontScale} = useCfg();
  const p1 = appear(frame, 5);
  const p2 = appear(frame, 22);
  const out = interpolate(frame, [sceneFrames(scenes[0]) - 20, sceneFrames(scenes[0])], [1, 0], {extrapolateLeft: 'clamp'});
  return (
    <Shell>
      <BackgroundWaves intensity={1.6} />
      <AbsoluteFill style={{justifyContent: 'center', alignItems: 'center', opacity: out}}>
        <img src={staticFile('branding/logo.png')} style={{height: 210, borderRadius: '50%', opacity: p1, transform: `scale(${0.7 + 0.3 * p1})`, boxShadow: '0 0 80px rgba(59,130,246,0.8)'}} alt="UGI" />
        <h1 style={{fontSize: 96 * fontScale, margin: '32px 0 0', color: GOLD, fontWeight: 900, opacity: p1, transform: `translateY(${(1 - p1) * 50}px)`}}>
          What Is Chemistry?
        </h1>
        <div style={{fontSize: 44 * fontScale, color: '#7dd3fc', fontWeight: 800, marginTop: 14, opacity: p2, letterSpacing: 2}}>
          Class 9 · Unit 1 · Lecture 1
        </div>
      </AbsoluteFill>
    </Shell>
  );
};

const OutroScene: React.FC = () => {
  const frame = useCurrentFrame();
  const {scene, fontScale} = useCfg();
  const p = appear(frame, 8);
  const p2 = appear(frame, 55);
  return (
    <Shell>
      <BackgroundWaves intensity={1.6} />
      <AbsoluteFill style={{justifyContent: 'center', alignItems: 'center'}}>
        <div style={{opacity: p, transform: `scale(${0.7 + 0.3 * p})`, textAlign: 'center'}}>
          <div style={{fontSize: 96, color: GREEN, fontWeight: 900}}>✓</div>
          <h1 style={{fontSize: 76 * fontScale, margin: '8px 0 0', color: GOLD, fontWeight: 900}}>{scene.title}</h1>
          <div style={{fontSize: 34 * fontScale, color: '#7dd3fc', marginTop: 12}}>{scene.subtitle}</div>
        </div>
        <div style={{fontSize: 44 * fontScale, color: '#e2e8f0', fontWeight: 800, marginTop: 54, opacity: p2}}>
          اللہ حافظ — ملتے ہیں اگلے لیکچر میں!
        </div>
      </AbsoluteFill>
    </Shell>
  );
};

const ContentScene: React.FC<{index: number; frames: number}> = ({index, frames}) => {
  const frame = useCurrentFrame();
  const {scene} = useCfg();
  const fadeOut = interpolate(frame, [frames - 15, frames], [1, 0], {extrapolateLeft: 'clamp'});
  const accent = scene.accent ?? CYAN;
  const isDefinition = scene.kind === 'definition';
  const isMap = scene.kind === 'why-branches';
  const isExercise = scene.kind === 'exercise';
  const isGlossary = scene.kind === 'glossary';
  const isMcq = scene.kind === 'mcq';
  return (
    <Shell>
      <BackgroundWaves intensity={0.5} />
      <div style={{opacity: fadeOut, height: '100%', display: 'flex', flexDirection: 'column'}}>
        <Header index={index} />
        <Title>{scene.title}</Title>
        {isExercise ? (
          <div style={{flex: 1, padding: '26px 60px 120px', display: 'flex', justifyContent: 'center'}}>
            <ExerciseVisual frames={frames} />
          </div>
        ) : isGlossary ? (
          <div style={{flex: 1, padding: '10px 80px 120px', display: 'flex', justifyContent: 'center'}}>
            <GlossaryVisual frames={frames} />
          </div>
        ) : isMcq ? (
          <div style={{flex: 1, padding: '16px 90px 120px', display: 'flex'}}>
            <McqVisual frames={frames} />
          </div>
        ) : isMap ? (
          <div style={{flex: 1, display: 'flex', justifyContent: 'center', alignItems: 'center', paddingBottom: 110}}>
            <HexagonMap frames={frames} />
          </div>
        ) : (
          <div style={{display: 'flex', flex: 1, padding: '18px 60px 120px', gap: 36, alignItems: 'center'}}>
            <div style={{flex: scene.kind === 'branch' || isDefinition ? '0 0 55%' : '1 1 100%'}}>
              <Bullets until={frames} />
              {isDefinition ? <DefinitionExtras /> : null}
            </div>
            {scene.kind === 'branch' || isDefinition ? (
              <div style={{flex: 1, display: 'flex', justifyContent: 'center', alignItems: 'center', flexDirection: 'column'}}>
                {isDefinition ? <Atom size={520} /> : null}
                {!isDefinition && scene.visual ? <BranchIcon kind={scene.visual} color={accent} size={380} /> : null}
                {!isDefinition ? (
                  <div style={{marginTop: 4, opacity: appear(frame, 30), fontSize: 30, fontWeight: 900, color: accent, letterSpacing: 1}}>
                    {scene.title.toUpperCase()}
                  </div>
                ) : null}
              </div>
            ) : null}
          </div>
        )}
        <UrduPanel />
        <GlobalProgress />
      </div>
    </Shell>
  );
};

const SceneAudio: React.FC = () => {
  const {scene} = useCfg();
  const entries = sceneEntries(scene);
  let t = 0;
  return (
    <>
      {entries.map((e, i) => {
        const start = t;
        t += framesOf(e.durationMs) + GAP;
        return (
          <Sequence key={i} from={start} durationInFrames={framesOf(e.durationMs)} layout="none">
            <Audio src={staticFile(`lecture1/audio/${e.file}`)} volume={1} />
          </Sequence>
        );
      })}
    </>
  );
};

const SceneView: React.FC<{scene: Scene; index: number; frames: number; start: number}> = ({scene, index, frames, start}) => {
  const cfg = {...defaultConfig, scene, sceneStart: start};
  let body: React.ReactNode;
  if (scene.kind === 'title') body = <TitleScene />;
  else if (scene.kind === 'outro') body = <OutroScene />;
  else body = <ContentScene index={index} frames={frames} />;
  return (
    <Ctx.Provider value={cfg}>
      {body}
      <SceneAudio />
    </Ctx.Provider>
  );
};

export const Lecture1Chemistry: React.FC<Lecture1Config> = (cfg) => {
  const sl = slide({direction: 'from-right'});
  const fd = fade();
  let start = 0;
  const laid = scenes.map((s) => {
    const frames = sceneFrames(s);
    const item = {s, frames, start};
    start += frames - TRANSITION;
    return item;
  });
  return (
    <AbsoluteFill style={{backgroundColor: '#04081f'}}>
      <TransitionSeries>
        {laid.map(({s, frames, start: st}, i) => (
          <React.Fragment key={s.id}>
            <TransitionSeries.Sequence durationInFrames={frames}>
              <SceneView scene={s} index={i + 1} frames={frames} start={st} />
            </TransitionSeries.Sequence>
            {i < laid.length - 1 ? (
              <TransitionSeries.Transition
                presentation={s.kind === 'title' || scenes[i + 1].kind === 'outro' || scenes[i + 1].kind === 'why-branches' ? sl : fd}
                timing={linearTiming({durationInFrames: TRANSITION})}
              />
            ) : null}
          </React.Fragment>
        ))}
      </TransitionSeries>
    </AbsoluteFill>
  );
};
