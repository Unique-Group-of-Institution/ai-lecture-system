export type Cut = {
  startMs: number;
  endMs: number;
  transcriptExcerpt: string;
  evidenceSha256: string;
};

export type LectureSlide = {
  position: number;
  title: string;
  claims: string[];
  caption: string;
  audioSrc: string;
  durationMs: number;
  cuts: Cut[];
  timelineStartFrame: number;
  narrationFrames: number;
  durationInFrames: number;
};

export type LectureProps = {
  schemaVersion: 1;
  compositionId: 'LectureAssembly' | 'SyntheticLectureSmoke';
  fps: 30;
  width: 1920;
  height: 1080;
  renderReference: string;
  publicDir?: string;
  slides: LectureSlide[];
  branding: {accentColor: string; institutionName: string};
  captions: {position: 'top' | 'bottom'; fontScale: number};
  transitionMs: number;
  holdAfterMs: number;
  totalDurationInFrames: number;
};
