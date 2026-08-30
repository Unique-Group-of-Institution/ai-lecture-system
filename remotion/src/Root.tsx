import React from 'react';
import {Composition} from 'remotion';
import {compositionFrames, Lecture} from './Lecture';
import type {LectureProps} from './types';

export const smokeProps: LectureProps = {
  schemaVersion: 1,
  compositionId: 'SyntheticLectureSmoke',
  fps: 30,
  width: 1920,
  height: 1080,
  renderReference: 'synthetic:smoke',
  slides: [
    {
      position: 1,
      title: 'Synthetic Motion / مصنوعی حرکت',
      claims: ['This fixture contains no teacher or institutional source media.', 'یہ صرف مصنوعی جانچ ہے۔'],
      caption: 'Synthetic English and Urdu caption. یہ مصنوعی اردو کیپشن ہے۔',
      audioSrc: 'smoke/silence.wav',
      durationMs: 1000,
      cuts: [],
      timelineStartFrame: 0,
      narrationFrames: 30,
      durationInFrames: 30,
    },
  ],
  branding: {accentColor: '#0057B8', institutionName: 'Synthetic Institution'},
  captions: {position: 'bottom', fontScale: 100},
  transitionMs: 0,
  holdAfterMs: 0,
  totalDurationInFrames: 30,
};

export const RemotionRoot: React.FC = () => (
  <>
    <Composition
      id="LectureAssembly"
      component={Lecture}
      width={1920}
      height={1080}
      fps={30}
      durationInFrames={30}
      defaultProps={smokeProps}
      calculateMetadata={({props}) => ({durationInFrames: compositionFrames(props as LectureProps)})}
    />
    <Composition
      id="SyntheticLectureSmoke"
      component={Lecture}
      width={1920}
      height={1080}
      fps={30}
      durationInFrames={30}
      defaultProps={smokeProps}
      calculateMetadata={({props}) => ({durationInFrames: compositionFrames(props as LectureProps)})}
    />
  </>
);
