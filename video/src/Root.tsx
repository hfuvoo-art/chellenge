import {Composition} from 'remotion';
import {SmokyPomegranate} from './SmokyPomegranate';
import {FPS, TOTAL_SECONDS} from './scenes';

export const Root: React.FC = () => (
  <Composition
    id="SmokyPomegranate"
    component={SmokyPomegranate}
    durationInFrames={TOTAL_SECONDS * FPS}
    fps={FPS}
    width={1920}
    height={1080}
  />
);
