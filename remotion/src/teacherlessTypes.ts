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

export type TeacherlessLectureProps = {
  schemaVersion: 1;
  compositionId: 'TeacherlessLecture' | 'TeacherlessLectureSmoke';
  fps: 30;
  width: 1920;
  height: 1080;
  renderReference: string;
  scenes: TeacherlessScene[];
  branding: {institutionName: string; accentColor: string; backgroundColor: string};
};

const ID = /^[A-Za-z][A-Za-z0-9_-]{0,63}$/u;
const COLOR = /^#[0-9A-Fa-f]{6}$/u;

export function validateTeacherlessLectureProps(value: unknown): TeacherlessLectureProps {
  if (!value || typeof value !== 'object') throw new Error('Teacherless lecture manifest must be an object.');
  const p = value as Partial<TeacherlessLectureProps>;
  if (p.schemaVersion !== 1 || (p.compositionId !== 'TeacherlessLecture' && p.compositionId !== 'TeacherlessLectureSmoke')) throw new Error('Unsupported teacherless lecture manifest version or composition.');
  if (p.fps !== 30 || p.width !== 1920 || p.height !== 1080) throw new Error('Teacherless lecture must use 1920x1080 at 30 fps.');
  if (!Array.isArray(p.scenes) || p.scenes.length === 0) throw new Error('Teacherless lecture requires at least one scene.');
  if (!p.branding || !COLOR.test(p.branding.accentColor) || !COLOR.test(p.branding.backgroundColor) || !p.branding.institutionName.trim()) throw new Error('Invalid teacherless lecture branding.');
  const seen = new Set<string>();
  for (const scene of p.scenes) {
    if (!scene || !ID.test(scene.id) || seen.has(scene.id)) throw new Error('Invalid or duplicate teacherless scene id.');
    seen.add(scene.id);
    if (!Number.isInteger(scene.durationMs) || scene.durationMs < 250) throw new Error('Teacherless scene duration must be at least 250ms.');
    if (!['concept', 'formula', 'diagram', 'workedExample', 'recap'].includes(scene.kind)) throw new Error('Unsupported teacherless scene kind.');
    if (!scene.title.trim() || !Array.isArray(scene.elements) || !Array.isArray(scene.animations)) throw new Error('Invalid teacherless scene.');
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

export const teacherlessDurationInFrames = (props: TeacherlessLectureProps) =>
  Math.max(1, props.scenes.reduce((sum, scene) => sum + Math.max(1, Math.round(scene.durationMs * props.fps / 1000)), 0));
