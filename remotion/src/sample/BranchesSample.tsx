import React from 'react';
import {
  AbsoluteFill,
  Audio,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
} from 'remotion';
import {TransitionSeries, linearTiming} from '@remotion/transitions';
import {fade} from '@remotion/transitions/fade';
import {slide} from '@remotion/transitions/slide';
import {BackgroundWaves} from '../ch12/visuals';

export const FPS = 30;
const TRANSITION = 15;

const TITLE_FRAMES = 201;
const CONCEPT_FRAMES = 1181;
const BRANCHES_FRAMES = 441;
const OUTRO_FRAMES = 302;
export const totalFrames = () =>
  TITLE_FRAMES + CONCEPT_FRAMES + BRANCHES_FRAMES + OUTRO_FRAMES - 3 * TRANSITION;

const CYAN = '#22d3ee';
const ORANGE = '#fb923c';
const GOLD = '#fbbf24';
const GREEN = '#22c55e';

const appear = (frame: number, from: number, delayMs = 0) =>
  spring({
    frame: frame - from - delayMs,
    fps: FPS,
    config: {damping: 18, stiffness: 120},
  });

const f = (sec: number) => Math.round(sec * FPS);

const Shell: React.FC<{children: React.ReactNode}> = ({children}) => (
  <AbsoluteFill
    style={{
      background:
        'radial-gradient(1200px 800px at 20% 10%, #0b1a5e 0%, #060d33 55%, #04081f 100%)',
      fontFamily: 'Arial, sans-serif',
      color: '#e2e8f0',
    }}
  >
    {children}
  </AbsoluteFill>
);

const Header: React.FC<{tag: string; page: string}> = ({tag, page}) => (
  <div style={{display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '26px 60px 0'}}>
    <div style={{display: 'flex', alignItems: 'center', gap: 22}}>
      <img src={staticFile('branding/logo.png')} style={{height: 92, borderRadius: '50%'}} alt="UGI" />
      <div>
        <div style={{fontSize: 26, fontWeight: 800, color: GOLD, letterSpacing: 1}}>
          UNIQUE GROUP OF INSTITUTIONS · LAHORE
        </div>
        <div style={{fontSize: 22, color: '#7dd3fc', marginTop: 4, fontWeight: 700}}>{tag}</div>
      </div>
    </div>
    <div style={{fontSize: 24, color: '#94a3b8'}}>{page}</div>
  </div>
);

const ProgressBar: React.FC<{frames: number}> = ({frames}) => {
  const frame = useCurrentFrame();
  const p = interpolate(frame, [0, frames], [0, 1], {extrapolateRight: 'clamp'});
  return (
    <div style={{position: 'absolute', left: 0, bottom: 0, width: '100%', height: 8, background: 'rgba(148,163,184,0.2)'}}>
      <div style={{width: `${p * 100}%`, height: '100%', background: `linear-gradient(90deg, ${CYAN}, ${GOLD})`}} />
    </div>
  );
};

const Card: React.FC<{children: React.ReactNode; start: number; accent?: string}> = ({children, start, accent = 'rgba(56,189,248,0.35)'}) => {
  const frame = useCurrentFrame();
  const p = appear(frame, start);
  return (
    <div
      style={{
        opacity: p,
        transform: `translateX(${(1 - p) * 70}px)`,
        background: 'rgba(13,26,84,0.6)',
        border: `1px solid ${accent}`,
        borderRadius: 16,
        padding: '12px 22px',
        marginBottom: 13,
      }}
    >
      {children}
    </div>
  );
};

const Chip: React.FC<{text: string; start: number; color: string}> = ({text, start, color}) => {
  const frame = useCurrentFrame();
  const p = appear(frame, start);
  return (
    <span
      style={{
        display: 'inline-block',
        opacity: p,
        transform: `scale(${0.5 + 0.5 * p})`,
        background: color,
        color: '#081033',
        fontWeight: 900,
        fontSize: 27,
        padding: '8px 22px',
        borderRadius: 999,
        marginRight: 16,
        boxShadow: `0 0 26px ${color}66`,
      }}
    >
      {text}
    </span>
  );
};

const Atom: React.FC = () => {
  const frame = useCurrentFrame();
  const p = appear(frame, 8);
  const spin = frame * 0.045;
  const orbits = [
    {rx: 300, ry: 110, tilt: 0, color: CYAN, phase: 0},
    {rx: 300, ry: 110, tilt: 60, color: ORANGE, phase: 2.1},
    {rx: 300, ry: 110, tilt: 120, color: GREEN, phase: 4.2},
  ];
  return (
    <svg width={720} height={720} style={{opacity: p, transform: `scale(${0.7 + 0.3 * p})`}}>
      <g transform="translate(360,360)">
        {orbits.map((o, i) => (
          <g key={i} transform={`rotate(${o.tilt})`}>
            <ellipse rx={o.rx} ry={o.ry} fill="none" stroke={o.color} strokeWidth={3} opacity={0.5} />
            <circle
              cx={o.rx * Math.cos(spin * (1 + i * 0.15) + o.phase)}
              cy={o.ry * Math.sin(spin * (1 + i * 0.15) + o.phase)}
              r={16}
              fill={o.color}
            />
            <circle
              cx={o.rx * Math.cos(spin * (1 + i * 0.15) + o.phase)}
              cy={o.ry * Math.sin(spin * (1 + i * 0.15) + o.phase)}
              r={30}
              fill={o.color}
              opacity={0.25}
            />
          </g>
        ))}
        <circle r={64 + 5 * Math.sin(frame * 0.12)} fill={GOLD} opacity={0.95} />
        <circle r={95} fill={GOLD} opacity={0.16} />
        <text y={12} textAnchor="middle" fontSize={34} fontWeight={900} fill="#081033" fontFamily="Arial">
          MATTER
        </text>
      </g>
    </svg>
  );
};

const PercentBars: React.FC<{start: number}> = ({start}) => {
  const frame = useCurrentFrame();
  const p = appear(frame, start);
  const bars = [
    {label: 'Element A', v: 0.65, color: CYAN},
    {label: 'Element B', v: 0.35, color: ORANGE},
  ];
  return (
    <div style={{opacity: p}}>
      {bars.map((b, i) => (
        <div key={i} style={{display: 'flex', alignItems: 'center', gap: 14, marginTop: 10}}>
          <div style={{width: 150, fontSize: 24, color: '#94a3b8'}}>{b.label}</div>
          <div style={{flex: 1, height: 22, background: 'rgba(148,163,184,0.18)', borderRadius: 11, overflow: 'hidden'}}>
            <div style={{width: `${interpolate(p, [0, 1], [0, b.v * 100])}%`, height: '100%', background: b.color, borderRadius: 11}} />
          </div>
          <div style={{width: 80, fontSize: 26, fontWeight: 900, color: b.color}}>{Math.round(b.v * 100 * p)}%</div>
        </div>
      ))}
    </div>
  );
};

const Lattice: React.FC<{start: number}> = ({start}) => {
  const frame = useCurrentFrame();
  const p = appear(frame, start);
  return (
    <svg width={430} height={130} style={{opacity: p}}>
      {[0, 1, 2, 3, 4].map((c) =>
        [0, 1].map((r) => {
          const q = appear(frame, start + 6 + c * 5 + r * 3);
          return (
            <g key={`${c}-${r}`}>
              <circle cx={40 + c * 88} cy={40 + r * 55} r={16 * q} fill={(c + r) % 2 === 0 ? CYAN : ORANGE} opacity={0.9} />
              {c < 4 ? <line x1={56 + c * 88} y1={40 + r * 55} x2={112 + c * 88} y2={40 + r * 55} stroke="#94a3b8" strokeWidth={3} opacity={q} /> : null}
              {r === 0 ? <line x1={40 + c * 88} y1={56 + 0} x2={40 + c * 88} y2={95} stroke="#94a3b8" strokeWidth={3} opacity={p} /> : null}
            </g>
          );
        }),
      )}
    </svg>
  );
};

const EnergyFlow: React.FC<{start: number}> = ({start}) => {
  const frame = useCurrentFrame();
  const p = appear(frame, start);
  const flow = (frame * 3) % 120;
  return (
    <svg width={430} height={104} style={{opacity: p}}>
      <rect x={0} y={28} width={110} height={40} rx={10} fill="rgba(34,211,238,0.18)" stroke={CYAN} strokeWidth={2} />
      <text x={55} y={55} textAnchor="middle" fontSize={22} fill="#e2e8f0" fontFamily="Arial" fontWeight={700}>Change</text>
      <rect x={320} y={28} width={110} height={40} rx={10} fill="rgba(251,146,60,0.18)" stroke={ORANGE} strokeWidth={2} />
      <text x={375} y={55} textAnchor="middle" fontSize={22} fill="#e2e8f0" fontFamily="Arial" fontWeight={700}>Change</text>
      {[0, 1, 2].map((i) => (
        <circle key={i} cx={130 + ((flow + i * 40) % 170)} cy={24} r={7} fill={GOLD} opacity={0.9} />
      ))}
      <text x={215} y={12} textAnchor="middle" fontSize={20} fill={GOLD} fontFamily="Arial">absorbed →</text>
      {[0, 1, 2].map((i) => (
        <circle key={i} cx={300 - ((flow + i * 40) % 170)} cy={78} r={7} fill={GREEN} opacity={0.9} />
      ))}
      <text x={215} y={96} textAnchor="middle" fontSize={20} fill={GREEN} fontFamily="Arial">← released</text>
    </svg>
  );
};

const ConceptScene: React.FC = () => {
  const frame = useCurrentFrame();
  const fadeOut = interpolate(frame, [CONCEPT_FRAMES - 15, CONCEPT_FRAMES], [1, 0], {extrapolateLeft: 'clamp'});
  const titleP = appear(frame, 6);
  return (
    <Shell>
      <BackgroundWaves intensity={0.5} />
      <div style={{opacity: fadeOut, height: '100%', display: 'flex', flexDirection: 'column'}}>
        <Header tag="CHEMISTRY · CLASS 9 · UNIT 1" page="01 / 02" />
        <div style={{padding: '20px 60px 0', opacity: titleP, transform: `translateY(${(1 - titleP) * 30}px)`}}>
          <h2 style={{fontSize: 52, margin: 0, color: GOLD, fontWeight: 900}}>What Is Chemistry?</h2>
        </div>
        <div style={{display: 'flex', flex: 1, padding: '10px 60px 30px', gap: 30, alignItems: 'center'}}>
          <div style={{flex: '0 0 42%', display: 'flex', justifyContent: 'center'}}>
            <Atom />
          </div>
          <div style={{flex: 1}}>
            <div style={{opacity: appear(frame, f(2.3) - 5), fontSize: 28, color: '#7dd3fc', fontWeight: 800, marginBottom: 8}}>
              The <span style={{color: CYAN, fontWeight: 900}}>branch of science</span> that deals with:
            </div>
            <div style={{marginBottom: 16, opacity: appear(frame, f(3.8) - 5)}}>
              <Chip text="PROPERTIES" start={f(3.8)} color={CYAN} />
              <Chip text="COMPOSITION" start={f(5.2)} color={GOLD} />
              <Chip text="STRUCTURE" start={f(6.6)} color={GREEN} />
              <span style={{fontSize: 26, color: '#94a3b8', whiteSpace: 'nowrap'}}>of substances</span>
            </div>
            <Card start={f(9.9)} accent="rgba(251,146,60,0.45)">
              <div style={{fontSize: 29, fontWeight: 800, color: ORANGE}}>
                Physical &amp; Chemical CHANGES in matter
              </div>
              <div style={{fontSize: 24, color: '#94a3b8', marginTop: 6, opacity: appear(frame, f(13.5))}}>
                ...and the <b style={{color: '#e2e8f0'}}>laws &amp; principles</b> that govern them
              </div>
            </Card>
            <Card start={f(18.6)} accent="rgba(34,211,238,0.45)">
              <div style={{fontSize: 27, fontWeight: 800, color: CYAN, marginBottom: 4}}>
                Composition = percentages of elements &amp; compounds
              </div>
              <PercentBars start={f(19.6)} />
            </Card>
            <Card start={f(26.9)} accent="rgba(34,197,94,0.45)">
              <div style={{fontSize: 27, fontWeight: 800, color: GREEN}}>
                Structure = arrangement of atoms in matter
              </div>
              <Lattice start={f(27.9)} />
            </Card>
            <Card start={f(31.5)} accent="rgba(251,191,36,0.5)">
              <div style={{fontSize: 27, fontWeight: 800, color: GOLD}}>
                Changes happen by energy absorption or release
              </div>
              <EnergyFlow start={f(32.3)} />
            </Card>
          </div>
        </div>
        <ProgressBar frames={CONCEPT_FRAMES} />
      </div>
    </Shell>
  );
};

const BRANCHES = [
  {label: 'Physical', sub: 'atoms & molecules', color: CYAN},
  {label: 'Inorganic', sub: 'metals, salts, acids', color: ORANGE},
  {label: 'Organic', sub: 'carbon compounds', color: GREEN},
  {label: 'Environmental', sub: 'air, soil, water', color: '#38bdf8'},
  {label: 'Analytical', sub: 'what is in a sample?', color: GOLD},
  {label: 'Biochemistry', sub: 'chemistry of life', color: '#a78bfa'},
  {label: 'Nuclear', sub: 'atomic nucleus', color: '#f472b6'},
  {label: 'Polymer', sub: 'giant molecules', color: '#4ade80'},
];

const BranchDiagram: React.FC<{audioFrames: number}> = ({audioFrames}) => {
  const frame = useCurrentFrame();
  const cx = 860;
  const cy = 330;
  const core = appear(frame, 10);
  return (
    <svg width={1720} height={680}>
      {BRANCHES.map((b, i) => {
        const ang = (Math.PI * 2 * i) / BRANCHES.length - Math.PI / 2;
        const nx = cx + 620 * Math.cos(ang);
        const ny = cy + 270 * Math.sin(ang);
        const start = f(1.2) + i * f(1.35);
        const p = appear(frame, start);
        const line = interpolate(p, [0, 1], [0, 1]);
        const pulse = i === Math.floor(((frame - f(12)) / 8) % BRANCHES.length) && frame > f(12)
          ? 1 + 0.12 * Math.sin((frame % 8) * 0.8)
          : 1;
        return (
          <g key={b.label}>
            <line
              x1={cx} y1={cy} x2={cx + (nx - cx) * line} y2={cy + (ny - cy) * line}
              stroke={b.color} strokeWidth={4} opacity={0.7}
            />
            <g opacity={p} transform={`translate(${nx},${ny}) scale(${0.6 + 0.4 * p})`}>
              <g transform={`scale(${pulse})`}>
                <rect x={-140} y={-38} width={280} height={76} rx={20} fill="rgba(8,15,55,0.85)" stroke={b.color} strokeWidth={3} />
                <text y={-4} textAnchor="middle" fontSize={30} fontWeight={900} fill={b.color} fontFamily="Arial">
                  {b.label}
                </text>
                <text y={26} textAnchor="middle" fontSize={20} fill="#94a3b8" fontFamily="Arial">
                  {b.sub}
                </text>
              </g>
            </g>
          </g>
        );
      })}
      <g opacity={core} transform={`translate(${cx},${cy}) scale(${0.6 + 0.4 * core})`}>
        <polygon
          points={Array.from({length: 6}, (_, i) => {
            const a = (Math.PI * 2 * i) / 6 - Math.PI / 6;
            return `${200 * Math.cos(a)},${200 * Math.sin(a)}`;
          }).join(' ')}
          fill="rgba(19,32,96,0.92)"
          stroke={GOLD}
          strokeWidth={5}
        />
        <text y={-8} textAnchor="middle" fontSize={46} fontWeight={900} fill={GOLD} fontFamily="Arial">
          CHEMISTRY
        </text>
        <text y={34} textAnchor="middle" fontSize={24} fill="#7dd3fc" fontFamily="Arial">
          8 distinct branches
        </text>
      </g>
    </svg>
  );
};

const BranchesScene: React.FC = () => {
  const frame = useCurrentFrame();
  const fadeOut = interpolate(frame, [BRANCHES_FRAMES - 15, BRANCHES_FRAMES], [1, 0], {extrapolateLeft: 'clamp'});
  return (
    <Shell>
      <BackgroundWaves intensity={0.6} />
      <div style={{opacity: fadeOut, height: '100%', display: 'flex', flexDirection: 'column'}}>
        <Header tag="CHEMISTRY · CLASS 9 · UNIT 1" page="02 / 02" />
        <div style={{padding: '14px 60px 0', opacity: appear(frame, 6)}}>
          <h2 style={{fontSize: 48, margin: 0, color: GOLD, fontWeight: 900}}>Branches of Chemistry</h2>
          <div style={{fontSize: 27, color: '#94a3b8', marginTop: 8, opacity: appear(frame, f(4.5))}}>
            A vast subject is divided into branches so scientists can <b style={{color: CYAN}}>focus</b>, make{' '}
            <b style={{color: GREEN}}>breakthroughs</b> and <b style={{color: ORANGE}}>advance</b> each field.
          </div>
        </div>
        <div style={{flex: 1, display: 'flex', justifyContent: 'center', alignItems: 'center'}}>
          <BranchDiagram audioFrames={BRANCHES_FRAMES} />
        </div>
        <ProgressBar frames={BRANCHES_FRAMES} />
      </div>
    </Shell>
  );
};

const TitleScene: React.FC = () => {
  const frame = useCurrentFrame();
  const p1 = appear(frame, 5);
  const p2 = appear(frame, 22);
  const out = interpolate(frame, [TITLE_FRAMES - 20, TITLE_FRAMES], [1, 0], {extrapolateLeft: 'clamp'});
  return (
    <Shell>
      <BackgroundWaves intensity={1.6} />
      <AbsoluteFill style={{justifyContent: 'center', alignItems: 'center', opacity: out}}>
        <img
          src={staticFile('branding/logo.png')}
          style={{height: 220, borderRadius: '50%', opacity: p1, transform: `scale(${0.7 + 0.3 * p1})`, boxShadow: '0 0 80px rgba(59,130,246,0.8)'}}
          alt="UGI"
        />
        <h1 style={{fontSize: 100, margin: '34px 0 0', color: GOLD, fontWeight: 900, opacity: p1, transform: `translateY(${(1 - p1) * 50}px)`}}>
          What Is Chemistry?
        </h1>
        <div style={{fontSize: 46, color: '#7dd3fc', fontWeight: 800, marginTop: 16, opacity: p2, letterSpacing: 2}}>
          Class 9 · Unit 1 · Lecture 1
        </div>
      </AbsoluteFill>
    </Shell>
  );
};

const OutroScene: React.FC = () => {
  const frame = useCurrentFrame();
  const p = appear(frame, 8);
  const p2 = appear(frame, 40);
  return (
    <Shell>
      <BackgroundWaves intensity={1.6} />
      <AbsoluteFill style={{justifyContent: 'center', alignItems: 'center'}}>
        <div style={{opacity: p, transform: `scale(${0.7 + 0.3 * p})`, textAlign: 'center'}}>
          <div style={{fontSize: 90, color: GREEN, fontWeight: 900}}>✓</div>
          <h1 style={{fontSize: 66, margin: '10px 0 0', color: GOLD, fontWeight: 900}}>This is the teaching style</h1>
          <div style={{fontSize: 36, color: '#7dd3fc', marginTop: 14}}>Animated diagrams · step-by-step build-ups · synced narration</div>
        </div>
        <div style={{fontSize: 40, color: '#e2e8f0', fontWeight: 800, marginTop: 60, opacity: p2}}>
          Allah Hafiz — milte hain next lecture mein!
        </div>
      </AbsoluteFill>
    </Shell>
  );
};

const WithAudio: React.FC<{src: string; children: React.ReactNode}> = ({src, children}) => (
  <>
    {children}
    <Audio src={staticFile(src)} volume={1} />
  </>
);

export const BranchesSample: React.FC = () => {
  const fd = fade();
  const sl = slide({direction: 'from-right'});
  return (
    <AbsoluteFill style={{backgroundColor: '#04081f'}}>
      <TransitionSeries>
        <TransitionSeries.Sequence durationInFrames={TITLE_FRAMES}>
          <WithAudio src="sample/title.wav"><TitleScene /></WithAudio>
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={sl} timing={linearTiming({durationInFrames: TRANSITION})} />
        <TransitionSeries.Sequence durationInFrames={CONCEPT_FRAMES}>
          <WithAudio src="sample/concept.wav"><ConceptScene /></WithAudio>
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={sl} timing={linearTiming({durationInFrames: TRANSITION})} />
        <TransitionSeries.Sequence durationInFrames={BRANCHES_FRAMES}>
          <WithAudio src="sample/branches.wav"><BranchesScene /></WithAudio>
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={fd} timing={linearTiming({durationInFrames: TRANSITION})} />
        <TransitionSeries.Sequence durationInFrames={OUTRO_FRAMES}>
          <WithAudio src="sample/outro.wav"><OutroScene /></WithAudio>
        </TransitionSeries.Sequence>
      </TransitionSeries>
    </AbsoluteFill>
  );
};
