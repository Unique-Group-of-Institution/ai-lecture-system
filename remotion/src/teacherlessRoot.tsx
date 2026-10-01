import React from 'react';
import {Composition} from 'remotion';
import {TeacherlessLecture} from './TeacherlessLecture';
import {teacherlessDurationInFrames, validateTeacherlessLectureProps} from './teacherlessTypes';
import {teacherlessSmokeProps} from './teacherlessSmokeProps';

export const TeacherlessRoot: React.FC = () => <Composition
  id="TeacherlessLecture"
  component={TeacherlessLecture}
  width={1920}
  height={1080}
  fps={30}
  durationInFrames={teacherlessDurationInFrames(teacherlessSmokeProps)}
  defaultProps={teacherlessSmokeProps}
  calculateMetadata={({props}) => {
    const valid = validateTeacherlessLectureProps(props);
    return {durationInFrames: teacherlessDurationInFrames(valid)};
  }}
/>;
