export type TeacherlessAnimation =
  | {type: 'fadeIn'; from?: number; to?: number}
  | {type: 'draw'; axis: 'x' | 'y'; from?: number; to?: number}
  | {type: 'highlight'; target: string; from?: number; to?: number}
  | {type: 'stepReveal'; stepCount: number; intervalMs?: number};

export type TeacherlessElement =
  | {kind: 'text'; id: string; text: string; x: number; y: number; width: number; fontSize: number; weight?: number}
  | {kind: 'formula'; id: string; expression: string; x: number; y: number; width: number; fontSize?: number}
  | {kind: 'diagram'; id: string; label: string; x: number; y: number; width: number; height: number}
  | {kind: 'callout'; id: string; text: string; x: number; y: number; width: number};

export type TeacherlessScene = {
  id: string;
  kind: 'concept' | 'formula' | 'diagram' | 'workedExample' | 'recap';
  durationMs: number;
  narrationAudioSrc?: string;
  narration?: {text: string; language: 'SOURCE' | 'BILINGUAL'; estimatedDurationMs: number};
  provenance?: {pageSnapshotId: number; pageNumber: number; startOffset: number; endOffset: number}[];
  title: string;
  elements: TeacherlessElement[];
  animations: TeacherlessAnimation[];
};

export type TeacherlessProduction = {
  introSrc?: string;
  introDurationMs?: number;
  outroSrc?: string;
  outroDurationMs?: number;
  logoSrc?: string;
  musicSrc?: string;
  musicVolume?: number;
};

export type TeacherlessLectureProps = {
  schemaVersion: 1;
  compositionId: 'TeacherlessLecture' | 'TeacherlessLectureSmoke';
  fps: 30;
  width: 1920;
  height: 1080;
  renderReference: string;
  scenes: TeacherlessScene[];
  branding: {institutionName: string; accentColor: string; backgroundColor: string};
  production?: TeacherlessProduction;
};

const ID = /^[A-Za-z][A-Za-z0-9_-]{0,63}$/u;
const COLOR = /^#[0-9A-Fa-f]{6}$/u;
const ASSET = /^[\w.-]+(?:\/[\w.-]+)*$/u;

const productionMs = (value: number | undefined, fallback: number) => {
  const ms = value ?? fallback;
  if (!Number.isInteger(ms) || ms < 250 || ms > 60_000) throw new Error('Invalid teacherless production duration.');
  return ms;
};

export function validateTeacherlessLectureProps(value: unknown): TeacherlessLectureProps {
  if (!value || typeof value !== 'object') throw new Error('Teacherless lecture manifest must be an object.');
  const p = value as Partial<TeacherlessLectureProps>;
  if (p.schemaVersion !== 1 || (p.compositionId !== 'TeacherlessLecture' && p.compositionId !== 'TeacherlessLectureSmoke')) throw new Error('Unsupported teacherless lecture manifest version or composition.');
  if (p.fps !== 30 || p.width !== 1920 || p.height !== 1080) throw new Error('Teacherless lecture must use 1920x1080 at 30 fps.');
  if (!Array.isArray(p.scenes) || p.scenes.length === 0) throw new Error('Teacherless lecture requires at least one scene.');
  if (!p.branding || !COLOR.test(p.branding.accentColor) || !COLOR.test(p.branding.backgroundColor) || !p.branding.institutionName.trim()) throw new Error('Invalid teacherless lecture branding.');
  if (p.production) {
    for (const key of ['introSrc', 'outroSrc', 'logoSrc', 'musicSrc'] as const) {
      const src = p.production[key];
      if (src !== undefined && (typeof src !== 'string' || !ASSET.test(src) || src.includes('..'))) throw new Error('Invalid teacherless production asset reference.');
    }
    if ((p.production.introSrc && !p.production.introDurationMs) || (p.production.outroSrc && !p.production.outroDurationMs)) throw new Error('Teacherless intro/outro require an explicit duration.');
    if (p.production.musicVolume !== undefined && !(p.production.musicVolume > 0 && p.production.musicVolume <= 1)) throw new Error('Invalid teacherless music volume.');
  }
  const seen = new Set<string>();
  for (const scene of p.scenes) {
    if (!scene || !ID.test(scene.id) || seen.has(scene.id)) throw new Error('Invalid or duplicate teacherless scene id.');
    seen.add(scene.id);
    if (!Number.isInteger(scene.durationMs) || scene.durationMs < 250) throw new Error('Teacherless scene duration must be at least 250ms.');
    if (!['concept', 'formula', 'diagram', 'workedExample', 'recap'].includes(scene.kind)) throw new Error('Unsupported teacherless scene kind.');
    if (!scene.title.trim() || !Array.isArray(scene.elements) || !Array.isArray(scene.animations)) throw new Error('Invalid teacherless scene.');
    if (scene.narration && (!scene.narration.text.trim() || !['SOURCE', 'BILINGUAL'].includes(scene.narration.language) || !Number.isInteger(scene.narration.estimatedDurationMs) || scene.narration.estimatedDurationMs < 250)) throw new Error('Invalid teacherless narration.');
    if (scene.provenance && (!Array.isArray(scene.provenance) || scene.provenance.some((ref) => !Number.isInteger(ref.pageSnapshotId) || !Number.isInteger(ref.pageNumber) || ref.startOffset < 0 || ref.endOffset <= ref.startOffset))) throw new Error('Invalid teacherless provenance.');
    const elementIds = new Set<string>();
    for (const element of scene.elements) {
      if (!element || !ID.test(element.id) || elementIds.has(element.id)) throw new Error('Invalid or duplicate teacherless element id.');
      elementIds.add(element.id);
    }
    for (const animation of scene.animations) {
      if (!animation || !['fadeIn', 'draw', 'highlight', 'stepReveal'].includes(animation.type)) throw new Error('Unsupported teacherless animation.');
      if (animation.type === 'stepReveal' && (!Number.isInteger(animation.stepCount) || animation.stepCount < 1 || animation.stepCount > 20)) throw new Error('Invalid teacherless step count.');
      if (animation.type === 'highlight' && !ID.test(animation.target)) throw new Error('Invalid teacherless highlight target.');
    }
  }
  return p as TeacherlessLectureProps;
}

export const teacherlessIntroFrames = (props: TeacherlessLectureProps) =>
  props.production?.introSrc ? Math.max(1, Math.round(productionMs(props.production.introDurationMs, 3000) * props.fps / 1000)) : 0;

export const teacherlessOutroFrames = (props: TeacherlessLectureProps) =>
  props.production?.outroSrc ? Math.max(1, Math.round(productionMs(props.production.outroDurationMs, 3000) * props.fps / 1000)) : 0;

export const teacherlessDurationInFrames = (props: TeacherlessLectureProps) =>
  teacherlessIntroFrames(props) + Math.max(1, props.scenes.reduce((sum, scene) => sum + Math.max(1, Math.round(scene.durationMs * props.fps / 1000)), 0)) + teacherlessOutroFrames(props);
