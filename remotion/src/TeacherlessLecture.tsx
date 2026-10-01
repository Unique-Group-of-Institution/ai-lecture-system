import React from 'react';
import {AbsoluteFill, Audio, Sequence, interpolate, staticFile, useCurrentFrame} from 'remotion';
import type {TeacherlessAnimation, TeacherlessElement, TeacherlessLectureProps, TeacherlessScene} from './teacherlessTypes';

const frames = (ms: number, fps: number) => Math.max(1, Math.round(ms * fps / 1000));

const animationOpacity = (animations: TeacherlessAnimation[], frame: number, total: number) => {
  const fade = animations.find((item) => item.type === 'fadeIn');
  if (!fade) return 1;
  const from = Math.max(0, Math.round((fade.from ?? 0) * total));
  const to = Math.max(from + 1, Math.round((fade.to ?? 0.12) * total));
  return interpolate(frame, [from, to], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
};

const Element: React.FC<{element: TeacherlessElement; scene: TeacherlessScene; frame: number; totalFrames: number}> = ({element, scene, frame, totalFrames}) => {
  const step = scene.animations.find((item) => item.type === 'stepReveal');
  const revealCount = step ? Math.min(step.stepCount, Math.floor(frame / Math.max(1, frames(step.intervalMs ?? 500, 30))) + 1) : Number.POSITIVE_INFINITY;
  const index = scene.elements.findIndex((item) => item.id === element.id);
  if (index >= revealCount) return null;

  const fade = animationOpacity(scene.animations, frame, totalFrames);
  const highlight = scene.animations.find((item) => item.type === 'highlight' && item.target === element.id);
  const draw = scene.animations.find((item) => item.type === 'draw');
  const drawProgress = draw ? interpolate(
    frame,
    [Math.round((draw.from ?? 0) * totalFrames), Math.max(1, Math.round((draw.to ?? 1) * totalFrames))],
    [0, 1],
    {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'},
  ) : 1;
  const base: React.CSSProperties = {
    position: 'absolute',
    left: element.x,
    top: element.y,
    width: element.width,
    boxSizing: 'border-box',
    opacity: fade,
    boxShadow: highlight ? '0 0 0 8px rgba(212,175,55,0.38)' : undefined,
  };

  if (element.kind === 'text') return <div style={{...base, fontSize: element.fontSize, fontWeight: element.weight ?? 500, lineHeight: 1.35}}>{element.text}</div>;
  if (element.kind === 'formula') return <div style={{...base, fontSize: element.fontSize ?? 56, fontWeight: 700, textAlign: 'center', fontFamily: 'Georgia, serif'}}>{element.expression}</div>;
  if (element.kind === 'callout') return <div style={{...base, padding: '20px 26px', border: '3px solid #D4AF37', borderRadius: 18, fontSize: 34, lineHeight: 1.35}}>{element.text}</div>;
  const drawStyle: React.CSSProperties = draw?.axis === 'y'
    ? {height: element.height * drawProgress, transformOrigin: 'top center'}
    : {height: element.height, transform: 'scaleX(' + drawProgress + ')', transformOrigin: 'left center'};
  return <div style={{...base, height: element.height, border: '5px solid #17365D', borderRadius: 22, ...drawStyle}}>
    <div style={{position: 'absolute', inset: 18, border: '2px dashed #D4AF37', borderRadius: 14}} />
    <div style={{position: 'absolute', left: 28, bottom: 24, fontSize: 28, fontWeight: 700}}>{element.label}</div>
  </div>;
};

const Scene: React.FC<{scene: TeacherlessScene; props: TeacherlessLectureProps; durationInFrames: number}> = ({scene, props, durationInFrames}) => {
  const frame = useCurrentFrame();
  const progress = frame / Math.max(1, durationInFrames - 1);
  return <AbsoluteFill style={{background: props.branding.backgroundColor, color: '#101828', fontFamily: 'Arial, "Noto Nastaliq Urdu", sans-serif'}}>
    <div style={{height: 18, background: props.branding.accentColor}} />
    <header style={{display: 'flex', justifyContent: 'space-between', padding: '32px 64px', fontSize: 25, fontWeight: 700}}><span>{props.branding.institutionName}</span><span>{scene.kind}</span></header>
    <main style={{position: 'absolute', inset: '125px 80px 80px'}}>
      <h1 style={{fontSize: 62, color: props.branding.accentColor, margin: '0 0 42px'}}>{scene.title}</h1>
      {scene.elements.map((element) => <Element key={element.id} element={element} scene={scene} frame={frame} totalFrames={durationInFrames} />)}
      <div style={{position: 'absolute', left: 0, right: 0, bottom: 0, height: 8, background: '#E5E7EB'}}><div style={{height: 8, width: (Math.round(progress * 100) + '%'), background: props.branding.accentColor}} /></div>
    </main>
    {scene.narrationAudioSrc ? <Audio src={staticFile(scene.narrationAudioSrc)} /> : null}
  </AbsoluteFill>;
};

export const TeacherlessLecture: React.FC<TeacherlessLectureProps> = (props) => {
  let from = 0;
  return <>{props.scenes.map((scene) => {
    const durationInFrames = frames(scene.durationMs, props.fps);
    const start = from;
    from += durationInFrames;
    return <Sequence key={scene.id} from={start} durationInFrames={durationInFrames}><Scene scene={scene} props={props} durationInFrames={durationInFrames} /></Sequence>;
  })}</>;
};
