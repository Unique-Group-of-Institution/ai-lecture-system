import React from 'react';
import {
  AbsoluteFill,
  Audio,
  OffthreadVideo,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import {TransitionSeries, linearTiming} from '@remotion/transitions';
import {fade} from '@remotion/transitions/fade';
import {slide} from '@remotion/transitions/slide';
import scenesData from '../../ch12-scenes.json';
import durations from '../../ch12-durations.json';
import Visual, {BackgroundWaves} from './visuals';

export const FPS = 30;
export const TRANSITION_FRAMES = 15;
export const INTRO_FRAMES = 169;
export const OUTRO_FRAMES = 99;
const PAD = 55;

type Scene = {
  id: number;
  part: string;
  kind: string;
  visual: string;
  title: string;
  subtitle: string;
  bullets: string[];
  answer: string;
  vo: string;
};

const scenes = scenesData.scenes as Scene[];

const durationsMap = durations as Record<string, number>;

export const sceneFrames = (s: Scene) =>
  Math.round(durationsMap[String(s.id)] * FPS) + PAD;

export const totalFrames = () => {
  const sum =
    INTRO_FRAMES +
    OUTRO_FRAMES +
    scenes.reduce((acc, s) => acc + sceneFrames(s), 0);
  const overlaps = TRANSITION_FRAMES * (scenes.length + 2 - 1);
  return sum - overlaps;
};

const appear = (frame: number, from: number, delayMs = 0) =>
  spring({
    frame: frame - from - delayMs,
    fps: FPS,
    config: {damping: 18, stiffness: 120},
  });

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

const Header: React.FC<{part: string; index: number; total: number}> = ({part, index, total}) => (
  <div style={{display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '26px 60px 0'}}>
    <div style={{display: 'flex', alignItems: 'center', gap: 22}}>
      <img src={staticFile('ch12/ugi-logo.png')} style={{height: 92, borderRadius: '50%'}} alt="UGI" />
      <div>
        <div style={{fontSize: 26, fontWeight: 800, color: '#fbbf24', letterSpacing: 1}}>
          UNIQUE GROUP OF INSTITUTIONS · LAHORE
        </div>
        <div style={{fontSize: 22, color: '#7dd3fc', marginTop: 4, fontWeight: 700}}>{part}</div>
      </div>
    </div>
    <div style={{fontSize: 24, color: '#94a3b8'}}>
      {String(index).padStart(2, '0')} / {total}
    </div>
  </div>
);

const Bullet: React.FC<{text: string; i: number; frame: number; start: number; step: number; check?: boolean}> = ({
  text,
  i,
  frame,
  start,
  step,
  check,
}) => {
  const p = appear(frame, start, i * step);
  return (
    <div
      style={{
        opacity: p,
        transform: `translateX(${(1 - p) * 60}px)`,
        display: 'flex',
        alignItems: 'flex-start',
        gap: 18,
        fontSize: 32,
        lineHeight: 1.4,
        marginBottom: 22,
        background: 'rgba(13,26,84,0.55)',
        border: '1px solid rgba(56,189,248,0.25)',
        borderRadius: 14,
        padding: '16px 24px',
      }}
    >
      {check ? (
        <span style={{color: '#22c55e', fontWeight: 900, fontSize: 30}}>✓</span>
      ) : (
        <span style={{color: '#22d3ee', fontWeight: 900, fontSize: 30}}>▸</span>
      )}
      <span>{text}</span>
    </div>
  );
};

const AnswerBadge: React.FC<{text: string; frame: number; start: number}> = ({text, frame, start}) => {
  const p = appear(frame, start);
  return (
    <div
      style={{
        position: 'absolute',
        right: 70,
        bottom: 60,
        opacity: p,
        transform: `scale(${0.6 + 0.4 * p})`,
        background: 'linear-gradient(135deg, #f59e0b, #ea580c)',
        color: '#1a1206',
        fontSize: 34,
        fontWeight: 900,
        padding: '18px 36px',
        borderRadius: 999,
        boxShadow: '0 0 40px rgba(251,146,60,0.6)',
      }}
    >
      {text}
    </div>
  );
};

const TitleScene: React.FC<{scene: Scene; frames: number}> = ({scene, frames}) => {
  const frame = useCurrentFrame();
  const p1 = appear(frame, 5);
  const p2 = appear(frame, 20);
  const out = interpolate(frame, [frames - 20, frames], [1, 0], {extrapolateLeft: 'clamp'});
  return (
    <Shell>
      <BackgroundWaves intensity={1.6} />
      <AbsoluteFill style={{justifyContent: 'center', alignItems: 'center', opacity: out}}>
        <img
          src={staticFile('ch12/ugi-logo.png')}
          style={{height: 240, borderRadius: '50%', opacity: p1, transform: `scale(${0.7 + 0.3 * p1})`, boxShadow: '0 0 80px rgba(59,130,246,0.8)'}}
          alt="UGI"
        />
        <h1 style={{fontSize: 96, margin: '36px 0 0', color: '#fbbf24', fontWeight: 900, opacity: p1, transform: `translateY(${(1 - p1) * 50}px)`}}>
          {scene.title}
        </h1>
        <div style={{fontSize: 52, color: '#7dd3fc', fontWeight: 800, marginTop: 18, opacity: p2, letterSpacing: 2}}>
          “{scene.subtitle}”
        </div>
        <div style={{fontSize: 28, color: '#94a3b8', marginTop: 40, opacity: p2}}>
          MCQs · Short Questions · CRQs · Numericals
        </div>
      </AbsoluteFill>
    </Shell>
  );
};

const DividerScene: React.FC<{scene: Scene; frames: number}> = ({scene, frames}) => {
  const frame = useCurrentFrame();
  const p = appear(frame, 5);
  const out = interpolate(frame, [frames - 20, frames], [1, 0], {extrapolateLeft: 'clamp'});
  return (
    <Shell>
      <BackgroundWaves intensity={1.2} />
      <AbsoluteFill style={{justifyContent: 'center', alignItems: 'center', opacity: out}}>
        <div style={{fontSize: 30, color: '#22d3ee', fontWeight: 800, letterSpacing: 6, opacity: p}}>
          {scene.part.toUpperCase()}
        </div>
        <h1 style={{fontSize: 88, margin: '20px 0 0', color: '#fbbf24', fontWeight: 900, opacity: p, transform: `translateY(${(1 - p) * 40}px)`, textAlign: 'center'}}>
          {scene.title}
        </h1>
        <div style={{fontSize: 40, color: '#94a3b8', marginTop: 16, opacity: p}}>{scene.subtitle}</div>
      </AbsoluteFill>
    </Shell>
  );
};

const ClosingScene: React.FC<{scene: Scene; frames: number}> = ({scene, frames}) => {
  const frame = useCurrentFrame();
  const p = appear(frame, 5);
  const out = interpolate(frame, [frames - 25, frames], [1, 0], {extrapolateLeft: 'clamp'});
  return (
    <Shell>
      <BackgroundWaves intensity={1.6} />
      <AbsoluteFill style={{justifyContent: 'center', alignItems: 'center', opacity: out}}>
        <div style={{opacity: p, transform: `scale(${0.7 + 0.3 * p})`}}>
          <div style={{fontSize: 110, fontWeight: 900, color: '#22c55e', textAlign: 'center'}}>✓</div>
          <h1 style={{fontSize: 84, margin: 0, color: '#fbbf24', fontWeight: 900, textAlign: 'center'}}>{scene.title}</h1>
          <div style={{fontSize: 40, color: '#7dd3fc', textAlign: 'center', marginTop: 10}}>{scene.subtitle}</div>
        </div>
        <div style={{marginTop: 50, width: 1100}}>
          {scene.bullets.map((b, i) => (
            <Bullet key={i} text={b} i={i} frame={frame} start={25} step={18} />
          ))}
        </div>
        <div style={{fontSize: 44, color: '#e2e8f0', fontWeight: 800, marginTop: 46, opacity: appear(frame, frames - 55)}}>
          Allah Hafiz — milte hain next lecture mein!
        </div>
      </AbsoluteFill>
    </Shell>
  );
};

const ContentScene: React.FC<{scene: Scene; frames: number; index: number}> = ({scene, frames, index}) => {
  const frame = useCurrentFrame();
  const hasVisual = scene.visual !== 'none';
  const bulletsStart = 30;
  const bulletStep = hasVisual || scene.bullets.length <= 4 ? Math.max(14, Math.floor((frames - 130) / Math.max(1, scene.bullets.length))) : 20;
  const answerStart = frames - 70;
  const titleP = appear(frame, 8);
  const fadeOut = interpolate(frame, [frames - 15, frames], [1, 0], {extrapolateLeft: 'clamp'});
  return (
    <Shell>
      <BackgroundWaves intensity={0.5} />
      <div style={{opacity: fadeOut, height: '100%', display: 'flex', flexDirection: 'column'}}>
        <Header part={scene.part} index={index} total={scenes.length + 2} />
        <div style={{padding: '26px 60px 0', opacity: titleP, transform: `translateY(${(1 - titleP) * 30}px)`}}>
          <h2 style={{fontSize: 48, margin: 0, color: '#fbbf24', fontWeight: 900, lineHeight: 1.25}}>{scene.title}</h2>
          {scene.kind === 'numeric' ? (
            <div style={{fontSize: 26, color: '#7dd3fc', marginTop: 6}}>Use v = fλ · f = 1/T · T = 1/f</div>
          ) : null}
        </div>
        <div style={{display: 'flex', flex: 1, padding: '26px 60px 40px', gap: 44, alignItems: 'flex-start'}}>
          <div style={{flex: hasVisual ? '0 0 46%' : '1 1 100%'}}>
            {scene.bullets.map((b, i) => (
              <Bullet key={i} text={b} i={i} frame={frame} start={bulletsStart} step={bulletStep} check={scene.kind === 'checklist'} />
            ))}
          </div>
          {hasVisual ? (
            <div style={{flex: 1, opacity: appear(frame, 20), transform: `translateX(${(1 - appear(frame, 20)) * 60}px)`}}>
              <Visual kind={scene.visual} w={996} h={396} />
            </div>
          ) : null}
        </div>
        {scene.answer ? <AnswerBadge text={scene.answer} frame={frame} start={answerStart} /> : null}
      </div>
    </Shell>
  );
};

const SceneView: React.FC<{scene: Scene; frames: number; index: number}> = ({scene, frames, index}) => {
  const audioSrc = staticFile(`ch12/audio/scene${String(scene.id).padStart(2, '0')}.mp3`);
  let body: React.ReactNode;
  if (scene.kind === 'title') body = <TitleScene scene={scene} frames={frames} />;
  else if (scene.kind === 'divider') body = <DividerScene scene={scene} frames={frames} />;
  else if (scene.kind === 'closing') body = <ClosingScene scene={scene} frames={frames} />;
  else body = <ContentScene scene={scene} frames={frames} index={index} />;
  return (
    <>
      {body}
      <Audio src={audioSrc} volume={1} />
    </>
  );
};

const IntroVideo: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps, durationInFrames} = useVideoConfig();
  const out = interpolate(frame, [durationInFrames - fps, durationInFrames], [1, 0], {extrapolateLeft: 'clamp'});
  return (
    <AbsoluteFill style={{backgroundColor: '#04081f'}}>
      <OffthreadVideo src={staticFile('ch12/intro.mp4')} style={{width: '100%', height: '100%', objectFit: 'cover'}} />
      <AbsoluteFill style={{backgroundColor: '#04081f', opacity: out}} />
    </AbsoluteFill>
  );
};

const OutroVideo: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const fadeIn = interpolate(frame, [0, fps * 0.5], [0, 1], {extrapolateRight: 'clamp'});
  return (
    <AbsoluteFill style={{backgroundColor: '#04081f'}}>
      <OffthreadVideo src={staticFile('ch12/outro.mp4')} style={{width: '100%', height: '100%', objectFit: 'cover', opacity: fadeIn}} />
    </AbsoluteFill>
  );
};

export const Chapter12Waves: React.FC = () => {
  const presentationFade = fade();
  const presentationSlide = slide({direction: 'from-right'});
  return (
    <AbsoluteFill style={{backgroundColor: '#04081f'}}>
      <TransitionSeries>
        <TransitionSeries.Sequence durationInFrames={INTRO_FRAMES}>
          <IntroVideo />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={presentationFade} timing={linearTiming({durationInFrames: TRANSITION_FRAMES})} />
        {scenes.map((scene, i) => {
          const frames = sceneFrames(scene);
          const isBreak = scene.kind === 'divider' || scene.kind === 'title' || scene.kind === 'closing';
          const next = scenes[i + 1];
          const transOut = !next
            ? presentationFade
            : next.kind === 'divider' || next.kind === 'closing'
              ? presentationSlide
              : presentationFade;
          return (
            <React.Fragment key={scene.id}>
              <TransitionSeries.Sequence durationInFrames={frames}>
                <SceneView scene={scene} frames={frames} index={i + 2} />
              </TransitionSeries.Sequence>
              <TransitionSeries.Transition
                presentation={isBreak ? presentationSlide : transOut}
                timing={linearTiming({durationInFrames: TRANSITION_FRAMES})}
              />
            </React.Fragment>
          );
        })}
        <TransitionSeries.Sequence durationInFrames={OUTRO_FRAMES}>
          <OutroVideo />
        </TransitionSeries.Sequence>
      </TransitionSeries>
    </AbsoluteFill>
  );
};
