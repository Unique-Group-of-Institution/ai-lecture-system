import type {TeacherlessLectureProps} from './teacherlessTypes';

export const teacherlessSmokeProps: TeacherlessLectureProps = {
  schemaVersion: 1,
  compositionId: 'TeacherlessLectureSmoke',
  fps: 30,
  width: 1920,
  height: 1080,
  renderReference: 'synthetic:teacherless-smoke',
  branding: {institutionName: 'Unique Group of Institutions', accentColor: '#17365D', backgroundColor: '#F8FAFC'},
  scenes: [
    {id: 'concept-01', kind: 'concept', durationMs: 1200, title: 'Current Electricity', elements: [
      {kind: 'text', id: 'definition', text: 'Electric current is the rate of flow of electric charge.', x: 80, y: 190, width: 1600, fontSize: 44},
      {kind: 'callout', id: 'unit', text: 'SI unit: ampere (A)', x: 110, y: 390, width: 720},
    ], animations: [{type: 'fadeIn'}]},
    {id: 'formula-01', kind: 'formula', durationMs: 1600, title: 'Formula: Electric Current', elements: [
      {kind: 'formula', id: 'formula', expression: 'I = Q / t', x: 420, y: 260, width: 1080, fontSize: 92},
      {kind: 'text', id: 'meaning', text: 'I = current    Q = charge    t = time', x: 420, y: 450, width: 1080, fontSize: 38},
    ], animations: [{type: 'fadeIn'}, {type: 'highlight', target: 'formula'}]},
    {id: 'diagram-01', kind: 'diagram', durationMs: 1400, title: 'Circuit Representation', elements: [
      {kind: 'diagram', id: 'circuit', label: 'Battery -> Wire -> Load', x: 260, y: 250, width: 1400, height: 360},
      {kind: 'text', id: 'direction', text: 'Show the conventional current direction with an arrow.', x: 360, y: 690, width: 1200, fontSize: 34},
    ], animations: [{type: 'fadeIn'}]},
  ],
};
