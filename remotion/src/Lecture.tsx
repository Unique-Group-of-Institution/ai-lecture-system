import React from 'react';
import {
  AbsoluteFill,
  Audio,
  Series,
  Sequence,
  interpolate,
  staticFile,
  useCurrentFrame,
} from 'remotion';
import type {Cut, LectureProps, LectureSlide} from './types';

const msToFrames = (milliseconds: number, fps: number) =>
  Math.max(0, Math.round((milliseconds / 1000) * fps));

const rtlText = (value: string) => /[\u0600-\u06ff]/u.test(value);

const keptIntervals = (durationMs: number, cuts: Cut[]) => {
  const intervals: Array<{startMs: number; endMs: number}> = [];
  let cursor = 0;
  for (const cut of cuts) {
    if (cut.startMs > cursor) intervals.push({startMs: cursor, endMs: cut.startMs});
    cursor = cut.endMs;
  }
  if (cursor < durationMs) intervals.push({startMs: cursor, endMs: durationMs});
  return intervals;
};

const SlideScene: React.FC<{
  slide: LectureSlide;
  props: LectureProps;
  durationInFrames: number;
}> = ({slide, props, durationInFrames}) => {
  const frame = useCurrentFrame();
  const direction = rtlText(`${slide.title} ${slide.caption}`) ? 'rtl' : 'ltr';
  const transitionFrames = Math.min(
    msToFrames(props.transitionMs, props.fps),
    Math.floor(durationInFrames / 2),
  );
  const opacity = transitionFrames === 0 ? 1 : Math.min(
    interpolate(frame, [0, transitionFrames], [0, 1], {
      extrapolateLeft: 'clamp',
      extrapolateRight: 'clamp',
    }),
    interpolate(frame, [durationInFrames - transitionFrames - 1, durationInFrames - 1], [1, 0], {
      extrapolateLeft: 'clamp',
      extrapolateRight: 'clamp',
    }),
  );
  let outputCursor = 0;
  return (
    <AbsoluteFill style={{backgroundColor: '#f8fafc', color: '#101828', fontFamily: 'Arial, "Noto Nastaliq Urdu", sans-serif'}}>
      <div style={{height: 18, backgroundColor: props.branding.accentColor}} />
      <header style={{display: 'flex', justifyContent: 'space-between', padding: '34px 64px 12px', fontSize: 25}}>
        <span>{props.branding.institutionName}</span>
        <span>{String(slide.position).padStart(2, '0')}</span>
      </header>
      <main dir={direction} style={{opacity, flex: 1, padding: '48px 100px 180px', textAlign: direction === 'rtl' ? 'right' : 'left'}}>
        <h1 style={{fontSize: 64, lineHeight: 1.25, margin: '0 0 42px', color: props.branding.accentColor}}>{slide.title}</h1>
        <ul style={{fontSize: 38, lineHeight: 1.55, margin: 0, paddingInlineStart: 55}}>
          {slide.claims.map((claim, index) => <li key={index} style={{marginBottom: 18}}>{claim}</li>)}
        </ul>
      </main>
      <div
        dir={rtlText(slide.caption) ? 'rtl' : 'ltr'}
        style={{
          position: 'absolute',
          left: 70,
          right: 70,
          [props.captions.position]: 35,
          borderRadius: 18,
          background: 'rgba(16,24,40,0.92)',
          color: 'white',
          padding: '20px 32px',
          textAlign: rtlText(slide.caption) ? 'right' : 'left',
          fontSize: 30 * (props.captions.fontScale / 100),
          lineHeight: 1.45,
        }}
      >
        {slide.caption}
      </div>
      {keptIntervals(slide.durationMs, slide.cuts).map((interval, index) => {
        const length = Math.max(1, msToFrames(interval.endMs - interval.startMs, props.fps));
        const from = outputCursor;
        outputCursor += length;
        return (
          <Sequence key={index} from={from} durationInFrames={length}>
            <Audio
              src={staticFile(slide.audioSrc)}
              trimBefore={msToFrames(interval.startMs, props.fps)}
              trimAfter={msToFrames(interval.endMs, props.fps)}
            />
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};

export const slideFrames = (slide: LectureSlide, props: LectureProps) => {
  return slide.durationInFrames;
};

export const compositionFrames = (props: LectureProps) => {
  return props.totalDurationInFrames;
};

export const Lecture: React.FC<LectureProps> = (props) => {
  return (
    <Series>
      {props.slides.map((slide) => {
        const duration = slideFrames(slide, props);
        return (
          <Series.Sequence key={slide.position} durationInFrames={duration}>
            <SlideScene slide={slide} props={props} durationInFrames={duration} />
          </Series.Sequence>
        );
      })}
    </Series>
  );
};
