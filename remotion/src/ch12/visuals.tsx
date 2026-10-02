import React from 'react';
import {interpolate, useCurrentFrame, useVideoConfig} from 'remotion';

const CYAN = '#22d3ee';
const ORANGE = '#fb923c';
const GOLD = '#fbbf24';
const DIM = 'rgba(148,163,184,0.35)';

type VisualProps = {w: number; h: number};

const useT = (speed = 1) => {
  const frame = useCurrentFrame();
  return frame * speed * 0.05;
};

const Label: React.FC<{
  x: number;
  y: number;
  text: string;
  color?: string;
  size?: number;
  anchor?: 'start' | 'middle' | 'end';
}> = ({x, y, text, color = '#e2e8f0', size = 22, anchor = 'middle'}) => (
  <text x={x} y={y} fill={color} fontSize={size} textAnchor={anchor} fontFamily="Arial" fontWeight={700}>
    {text}
  </text>
);

const sinePath = (
  w: number,
  mid: number,
  amp: number,
  k: number,
  phase: number,
  steps = 60,
) => {
  let d = '';
  for (let i = 0; i <= steps; i++) {
    const x = (i / steps) * w;
    const y = mid - amp * Math.sin(k * x - phase);
    d += `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`;
  }
  return d;
};

const Frame: React.FC<{children: React.ReactNode; title?: string}> = ({children, title}) => (
  <g>
    <rect x={2} y={2} width={996} height={396} rx={18} fill="rgba(8,15,55,0.65)" stroke="rgba(34,211,238,0.35)" strokeWidth={2} />
    {title ? <Label x={500} y={40} text={title} color={CYAN} size={24} /> : null}
    {children}
  </g>
);

const TransverseWave: React.FC<VisualProps & {amp?: number; color?: string; labels?: boolean}> = ({
  w,
  h,
  amp = 70,
  color = CYAN,
  labels = false,
}) => {
  const t = useT(1.2);
  const mid = h / 2;
  const k = 0.02;
  const crestX = (Math.PI / 2 + t) / k;
  const troughX = (3 * Math.PI / 2 + t) / k;
  return (
    <g>
      <line x1={0} y1={mid} x2={w} y2={mid} stroke={DIM} strokeWidth={2} strokeDasharray="8 8" />
      <path d={sinePath(w, mid, amp, k, t)} stroke={color} strokeWidth={5} fill="none" />
      <path d={sinePath(w, mid, amp, k, t)} stroke={color} strokeWidth={14} fill="none" opacity={0.15} />
      {labels ? (
        <g>
          {crestX < w - 60 ? (
            <g>
              <circle cx={crestX} cy={mid - amp} r={8} fill={GOLD} />
              <Label x={crestX} y={mid - amp - 18} text="CREST" color={GOLD} size={26} />
            </g>
          ) : null}
          {troughX < w - 60 ? (
            <g>
              <circle cx={troughX} cy={mid + amp} r={8} fill={ORANGE} />
              <Label x={troughX} y={mid + amp + 36} text="TROUGH" color={ORANGE} size={26} />
            </g>
          ) : null}
        </g>
      ) : null}
    </g>
  );
};

const LongitudinalParticles: React.FC<VisualProps & {rows?: number}> = ({w, h, rows = 3}) => {
  const t = useT(1.4);
  const k = 0.025;
  const dots: React.ReactNode[] = [];
  for (let r = 0; r < rows; r++) {
    const y = (h / (rows + 1)) * (r + 1);
    for (let i = 0; i <= 34; i++) {
      const base = (i / 34) * w;
      const dx = 26 * Math.sin(k * base - t);
      const squeeze = 1 - 0.45 * Math.abs(Math.cos(k * base - t));
      dots.push(
        <circle key={`${r}-${i}`} cx={base + dx} cy={y} r={7 * squeeze + 2} fill={r === 1 ? CYAN : 'rgba(34,211,238,0.55)'} />,
      );
    }
  }
  return (
    <g>
      {dots}
      <g>
        <line x1={w - 170} y1={h - 34} x2={w - 60} y2={h - 34} stroke={GOLD} strokeWidth={5} />
        <path d={`M${w - 60},${h - 34} l -18,-9 m 18,9 l -18,9`} stroke={GOLD} strokeWidth={5} fill="none" />
        <Label x={w - 115} y={h - 48} text="Wave" color={GOLD} size={22} />
      </g>
      <Label x={80} y={h - 34} text="←→ vibration" color={CYAN} size={22} anchor="start" />
    </g>
  );
};

const AmplitudePair: React.FC<VisualProps> = ({w, h}) => {
  const mid1 = h * 0.3;
  const mid2 = h * 0.75;
  return (
    <g>
      <TransverseWave w={w} h={h * 0.32} amp={22} color="rgba(148,163,184,0.9)" />
      <g transform={`translate(0, ${h * 0.45})`}>
        <TransverseWave w={w} h={h * 0.55} amp={95} color={ORANGE} />
      </g>
      <Label x={w - 30} y={mid1} text="Small amplitude → Less energy" color="#94a3b8" size={24} anchor="end" />
      <Label x={w - 30} y={mid2 + 10} text="Large amplitude → More energy" color={GOLD} size={24} anchor="end" />
    </g>
  );
};

const MediumSplit: React.FC<VisualProps> = ({w, h}) => {
  const t = useT(1.1);
  return (
    <g>
      <rect x={20} y={60} width={w / 2 - 40} height={h - 100} rx={14} fill="rgba(34,211,238,0.08)" stroke={CYAN} strokeWidth={2} />
      <rect x={w / 2 + 20} y={60} width={w / 2 - 40} height={h - 100} rx={14} fill="rgba(251,146,60,0.08)" stroke={ORANGE} strokeWidth={2} />
      <Label x={w / 4} y={105} text="MECHANICAL WAVE" color={CYAN} size={26} />
      <Label x={(3 * w) / 4} y={105} text="ELECTROMAGNETIC WAVE" color={ORANGE} size={26} />
      <Label x={w / 4} y={140} text="Requires a medium" color="#e2e8f0" size={22} />
      <Label x={(3 * w) / 4} y={140} text="No medium needed (can cross vacuum)" color="#e2e8f0" size={22} />
      <g transform={`translate(${w / 4 - 130}, 170)`}>
        <path d={sinePath(260, 70, 42, 0.05, t)} stroke={CYAN} strokeWidth={4} fill="none" />
        {[0, 1, 2, 3, 4, 5].map((i) => (
          <circle key={i} cx={20 + i * 45} cy={130} r={5} fill="rgba(148,163,184,0.8)" />
        ))}
        <Label x={130} y={160} text="medium: air / water / solid" color="#94a3b8" size={20} />
      </g>
      <g transform={`translate(${(3 * w) / 4 - 130}, 170)`}>
        <path d={sinePath(260, 70, 42, 0.05, t)} stroke={ORANGE} strokeWidth={4} fill="none" />
        <path d={sinePath(260, 70, 42, 0.05, t + Math.PI / 2)} stroke={GOLD} strokeWidth={3} fill="none" opacity={0.7} />
        <Label x={130} y={160} text="X-rays · light · radio waves" color="#94a3b8" size={20} />
      </g>
    </g>
  );
};

const WavefrontScene: React.FC<VisualProps> = ({w, h}) => {
  const t = useT(1.2);
  const k = 0.03;
  const dots: React.ReactNode[] = [];
  for (let r = 0; r < 4; r++) {
    const y = 90 + r * ((h - 140) / 3);
    for (let i = 0; i <= 20; i++) {
      const x = 40 + (i / 20) * (w - 80);
      const dy = 34 * Math.sin(k * x - t);
      dots.push(<circle key={`${r}-${i}`} cx={x} cy={y + dy} r={6} fill={CYAN} opacity={0.85} />);
    }
  }
  const lineYs = [0, 1, 2, 3].map((r) => 90 + r * ((h - 140) / 3));
  return (
    <g>
      {dots}
      {lineYs.map((y, i) => (
        <path key={i} d={sinePath(w - 80, y, 34, k, t)} transform="translate(40,0)" stroke="rgba(251,191,36,0.9)" strokeWidth={3} fill="none" strokeDasharray="10 8" />
      ))}
      <Label x={w / 2} y={h - 22} text="Points vibrating in the SAME phase are joined by an imaginary surface" color={GOLD} size={22} />
    </g>
  );
};

const RefractionScene: React.FC<VisualProps> = ({w, h}) => {
  const frame = useCurrentFrame();
  const shift = (frame * 1.6) % 120;
  const bx = w * 0.55;
  const lines: React.ReactNode[] = [];
  for (let i = -1; i < 10; i++) {
    const x = i * 120 + shift;
    if (x < bx) {
      lines.push(<line key={`d${i}`} x1={x} y1={50} x2={x} y2={h - 50} stroke={CYAN} strokeWidth={5} opacity={0.85} />);
    } else {
      const x2 = bx + (x - bx) * 0.55;
      lines.push(<line key={`s${i}`} x1={x2} y1={50} x2={x2} y2={h - 50} stroke={ORANGE} strokeWidth={5} opacity={0.85} />);
    }
  }
  return (
    <g>
      <rect x={0} y={40} width={bx} height={h - 80} fill="rgba(34,211,238,0.06)" />
      <rect x={bx} y={40} width={w - bx} height={h - 80} fill="rgba(251,146,60,0.08)" />
      <line x1={bx} y1={40} x2={bx} y2={h - 40} stroke="#e2e8f0" strokeWidth={3} strokeDasharray="12 10" />
      {lines}
      <Label x={bx / 2} y={70} text="DEEP water — fast" color={CYAN} size={24} />
      <Label x={bx + (w - bx) / 2} y={70} text="SHALLOW water — slow" color={ORANGE} size={24} />
      <Label x={w / 2} y={h - 22} text="Speed changes → direction bends = Refraction" color={GOLD} size={22} />
    </g>
  );
};

const TsunamiScene: React.FC<VisualProps> = ({w, h}) => {
  const t = useT(1);
  const steps = 70;
  let d = '';
  for (let i = 0; i <= steps; i++) {
    const x = (i / steps) * w;
    const p = i / steps;
    const amp = 12 + 70 * Math.pow(p, 2.2);
    const k = 0.02 + 0.05 * Math.pow(p, 1.6);
    const y = h * 0.55 - amp * Math.sin(k * x - t);
    d += `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`;
  }
  const bed = `M0,${h * 0.8} L${w * 0.55},${h * 0.8} L${w * 0.8},${h * 0.66} L${w},${h * 0.5} L${w},${h} L0,${h} Z`;
  return (
    <g>
      <path d={`${d} L${w},${h} L0,${h} Z`} fill="rgba(34,211,238,0.14)" />
      <path d={d} stroke={CYAN} strokeWidth={5} fill="none" />
      <path d={bed} fill="#334155" stroke="#64748b" strokeWidth={3} />
      <Label x={w * 0.25} y={h * 0.8 - 20} text="Deep ocean: long wavelength, low height" color="#94a3b8" size={20} />
      <Label x={w * 0.78} y={h * 0.35} text="Speed ↓  Wavelength ↓  Height ↑" color={GOLD} size={24} />
    </g>
  );
};

const DiffractionScene: React.FC<VisualProps> = ({w, h}) => {
  const frame = useCurrentFrame();
  const gap = h / 2;
  const wallX = w * 0.42;
  const planes: React.ReactNode[] = [];
  for (let i = 0; i < 6; i++) {
    const x = ((frame * 1.8 + i * 90) % 560) * (wallX / 560);
    if (x < wallX - 6) {
      planes.push(<line key={i} x1={x} y1={40} x2={x} y2={h - 40} stroke={CYAN} strokeWidth={4} opacity={0.8} />);
    }
  }
  const circ: React.ReactNode[] = [];
  for (let i = 0; i < 6; i++) {
    const r = ((frame * 2.2 + i * 70) % 460) + 12;
    circ.push(
      <path key={i} d={`M${wallX + 10},${gap - r} a ${r} ${r} 0 0 1 0 ${2 * r}`} stroke={ORANGE} strokeWidth={4} fill="none" opacity={Math.max(0, 1 - r / 460)} />,
    );
  }
  return (
    <g>
      {planes}
      <line x1={wallX} y1={30} x2={wallX} y2={gap - 55} stroke="#e2e8f0" strokeWidth={10} strokeLinecap="round" />
      <line x1={wallX} y1={gap + 55} x2={wallX} y2={h - 30} stroke="#e2e8f0" strokeWidth={10} strokeLinecap="round" />
      {circ}
      <circle cx={wallX} cy={gap} r={7} fill={GOLD} />
      <Label x={wallX * 0.5} y={h - 22} text="Plane wavefronts" color={CYAN} size={22} />
      <Label x={wallX + (w - wallX) * 0.55} y={h - 22} text="Wave spreads after the gap = Diffraction" color={ORANGE} size={22} />
    </g>
  );
};

const SlitScene: React.FC<VisualProps> = ({w, h}) => {
  const frame = useCurrentFrame();
  const gap = h / 2;
  const wallX = w * 0.42;
  const planes: React.ReactNode[] = [];
  for (let i = 0; i < 6; i++) {
    const x = ((frame * 1.6 + i * 90) % 560) * (wallX / 560);
    if (x < wallX - 6) {
      planes.push(<line key={i} x1={x} y1={40} x2={x} y2={h - 40} stroke={CYAN} strokeWidth={4} opacity={0.8} />);
    }
  }
  const circ: React.ReactNode[] = [];
  for (let i = 0; i < 5; i++) {
    const r = ((frame * 2 + i * 85) % 420) + 10;
    circ.push(
      <circle key={i} cx={wallX + 8} cy={gap} r={r} stroke={ORANGE} strokeWidth={4} fill="none" opacity={Math.max(0, 0.9 - r / 420)} />,
    );
  }
  return (
    <g>
      {planes}
      <line x1={wallX} y1={30} x2={wallX} y2={gap - 16} stroke="#e2e8f0" strokeWidth={10} strokeLinecap="round" />
      <line x1={wallX} y1={gap + 16} x2={wallX} y2={h - 30} stroke="#e2e8f0" strokeWidth={10} strokeLinecap="round" />
      {circ}
      <Label x={wallX * 0.5} y={h - 22} text="Wavelength >> slit size" color={CYAN} size={22} />
      <Label x={wallX + (w - wallX) * 0.55} y={h - 22} text="Circular wavefronts → MAXIMUM diffraction" color={ORANGE} size={22} />
    </g>
  );
};

const EnergyScene: React.FC<VisualProps> = ({w, h}) => {
  const frame = useCurrentFrame();
  const mid = h / 2;
  const t = frame * 0.06;
  const pulseX = 60 + ((frame * 3) % (w - 120));
  return (
    <g>
      <path d={sinePath(w, mid, 60, 0.025, t)} stroke={CYAN} strokeWidth={4} fill="none" />
      {[...Array(14)].map((_, i) => {
        const x = 40 + (i / 13) * (w - 80);
        const y = mid - 60 * Math.sin(0.025 * x - t);
        return <circle key={i} cx={x} cy={y} r={7} fill="#94a3b8" />;
      })}
      <circle cx={pulseX} cy={mid - 60 * Math.sin(0.025 * pulseX - t)} r={16} fill={GOLD} opacity={0.9} />
      <circle cx={pulseX} cy={mid - 60 * Math.sin(0.025 * pulseX - t)} r={28} fill="none" stroke={GOLD} strokeWidth={3} opacity={0.5} />
      <Label x={60} y={h - 26} text="Point A" color="#e2e8f0" size={24} anchor="start" />
      <Label x={w - 60} y={h - 26} text="Point B" color="#e2e8f0" size={24} anchor="end" />
      <Label x={w / 2} y={44} text="Energy moves → particles only oscillate about their positions" color={GOLD} size={22} />
    </g>
  );
};

const SpaceScene: React.FC<VisualProps> = ({w, h}) => {
  const t = useT(1.2);
  return (
    <g>
      {[...Array(40)].map((_, i) => (
        <circle key={i} cx={(i * 173) % w} cy={(i * 97) % h} r={2 + (i % 3)} fill="rgba(255,255,255,0.5)" />
      ))}
      <g transform="translate(0, 60)">
        <path d={sinePath(w * 0.55, 80, 40, 0.05, t)} stroke={ORANGE} strokeWidth={4} fill="none" />
        <line x1={w * 0.58} y1={10} x2={w * 0.58} y2={150} stroke="#e2e8f0" strokeWidth={4} strokeDasharray="10 8" />
        <text x={w * 0.62} y={95} fontSize={60} fill="#ef4444" fontFamily="Arial" fontWeight={900}>✕</text>
        <Label x={w * 0.78} y={90} text="SOUND — blocked (no medium)" color="#fca5a5" size={24} anchor="start" />
      </g>
      <g transform={`translate(0, ${h / 2 + 20})`}>
        <path d={sinePath(w * 0.55, 80, 40, 0.05, t)} stroke={GOLD} strokeWidth={4} fill="none" />
        <path d={sinePath(w, 80, 40, 0.05, t)} stroke={GOLD} strokeWidth={4} fill="none" opacity={0.9} />
        <text x={w * 0.62} y={95} fontSize={60} fill="#22c55e" fontFamily="Arial" fontWeight={900}>✓</text>
        <Label x={w * 0.78} y={90} text="LIGHT — passes through vacuum" color={GOLD} size={24} anchor="start" />
      </g>
      <Label x={w * 0.29} y={h - 20} text="VACUUM / SPACE" color="#94a3b8" size={24} />
    </g>
  );
};

const WaveTypesScene: React.FC<VisualProps> = ({w, h}) => {
  const t = useT(1.2);
  const half = w / 2;
  return (
    <g>
      <line x1={half} y1={50} x2={half} y2={h - 50} stroke={DIM} strokeWidth={2} />
      <g transform={`translate(${half * 0.08}, 30)`}>
        <Label x={half * 0.42} y={30} text="TRANSVERSE" color={CYAN} size={26} />
        <path d={sinePath(half * 0.84, 130, 55, 0.035, t)} stroke={CYAN} strokeWidth={4} fill="none" />
        {[...Array(9)].map((_, i) => {
          const x = 12 + (i / 8) * (half * 0.84 - 24);
          return <line key={i} x1={x} y1={130 - 40 * Math.sin(0.035 * x - t)} x2={x} y2={130 - 40 * Math.sin(0.035 * x - t) - 24} stroke="#94a3b8" strokeWidth={3} />;
        })}
        <Label x={half * 0.42} y={h - 70} text="particles ↑↓ · wave →" color="#94a3b8" size={20} />
        <Label x={half * 0.42} y={h - 40} text="e.g. water wave" color={GOLD} size={20} />
      </g>
      <g transform={`translate(${half * 1.08}, 30)`}>
        <Label x={half * 0.42} y={30} text="LONGITUDINAL" color={ORANGE} size={26} />
        <g transform="translate(0, 90)">
          <LongitudinalParticles w={half * 0.84} h={80} rows={2} />
        </g>
        <Label x={half * 0.42} y={h - 70} text="particles ↔ · wave →" color="#94a3b8" size={20} />
        <Label x={half * 0.42} y={h - 40} text="e.g. sound wave" color={GOLD} size={20} />
      </g>
    </g>
  );
};

const RopeScene: React.FC<VisualProps> = ({w, h}) => {
  const frame = useCurrentFrame();
  const t = frame * 0.07;
  const mid = h / 2;
  const steps = 60;
  let d = '';
  for (let i = 0; i <= steps; i++) {
    const x = 120 + (i / steps) * (w - 200);
    const decay = Math.exp(-((i / steps) * 0.35));
    const y = mid - 80 * decay * Math.sin(0.03 * x - t);
    d += `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`;
  }
  const handY = mid - 80 * Math.sin(-t);
  return (
    <g>
      <path d={d} stroke={ORANGE} strokeWidth={7} fill="none" strokeLinecap="round" />
      <circle cx={95} cy={handY} r={26} fill={GOLD} />
      <Label x={95} y={h - 40} text="hand shakes" color={GOLD} size={22} />
      <line x1={w - 70} y1={mid - 110} x2={w - 70} y2={mid + 110} stroke="#64748b" strokeWidth={8} />
      <g>
        <line x1={w * 0.62} y1={mid - 130} x2={w - 120} y2={mid - 130} stroke={CYAN} strokeWidth={5} />
        <path d={`M${w - 120},${mid - 130} l -18,-9 m 18,9 l -18,9`} stroke={CYAN} strokeWidth={5} fill="none" />
        <Label x={w * 0.78} y={mid - 148} text="wave direction" color={CYAN} size={22} />
      </g>
      <g>
        <line x1={w * 0.45} y1={mid - 80} x2={w * 0.45} y2={mid + 80} stroke={GOLD} strokeWidth={5} />
        <path d={`M${w * 0.45},${mid + 80} l -9,-18 m 9,18 l 9,-18`} stroke={GOLD} strokeWidth={5} fill="none" />
        <Label x={w * 0.45 - 90} y={mid} text="particles ↑↓" color={GOLD} size={22} anchor="end" />
      </g>
    </g>
  );
};

const Visual: React.FC<{kind: string; w: number; h: number; title?: string}> = ({kind, w, h, title}) => {
  let inner: React.ReactNode = null;
  if (kind === 'longitudinal') inner = <LongitudinalParticles w={w} h={h} />;
  else if (kind === 'transverse') inner = <TransverseWave w={w} h={h} labels />;
  else if (kind === 'amplitudes') inner = <AmplitudePair w={w} h={h} />;
  else if (kind === 'medium') inner = <MediumSplit w={w} h={h} />;
  else if (kind === 'wavefront') inner = <WavefrontScene w={w} h={h} />;
  else if (kind === 'refraction') inner = <RefractionScene w={w} h={h} />;
  else if (kind === 'tsunami') inner = <TsunamiScene w={w} h={h} />;
  else if (kind === 'diffraction') inner = <DiffractionScene w={w} h={h} />;
  else if (kind === 'slit') inner = <SlitScene w={w} h={h} />;
  else if (kind === 'energy') inner = <EnergyScene w={w} h={h} />;
  else if (kind === 'space') inner = <SpaceScene w={w} h={h} />;
  else if (kind === 'wtypes') inner = <WaveTypesScene w={w} h={h} />;
  else if (kind === 'rope') inner = <RopeScene w={w} h={h} />;
  if (!inner) return null;
  return (
    <svg width={w + 4} height={h + 4}>
      <Frame title={title}>{inner}</Frame>
    </svg>
  );
};

export const BackgroundWaves: React.FC<{intensity?: number}> = ({intensity = 1}) => {
  const t = useT(0.6);
  const {width, height} = useVideoConfig();
  return (
    <svg width={width} height={height} style={{position: 'absolute', opacity: 0.14 * intensity}}>
      {[0.25, 0.5, 0.75].map((f, i) => (
        <path key={i} d={sinePath(width, height * f, 60 + i * 20, 0.004 + i * 0.002, t + i * 2)} stroke={i === 1 ? ORANGE : CYAN} strokeWidth={3} fill="none" />
      ))}
    </svg>
  );
};

export default Visual;
