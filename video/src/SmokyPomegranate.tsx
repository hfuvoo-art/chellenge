import {
  AbsoluteFill,
  Easing,
  Img,
  Sequence,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import {Audio, Video} from '@remotion/media';
import {loadFont} from '@remotion/google-fonts/CormorantGaramond';
import {LOGO, MUSIC, SCENES, SFX, STAGE_LOOK, Scene, TITLES, VOICE} from './scenes';

const {fontFamily} = loadFont('normal', {weights: ['400', '500'], subsets: ['cyrillic', 'latin']});

const FADE = 0.6; // секунды наплыва между сценами
const ease = Easing.bezier(0.16, 1, 0.3, 1);

export const SmokyPomegranate: React.FC = () => {
  const {fps} = useVideoConfig();
  return (
    <AbsoluteFill style={{backgroundColor: '#0d0706'}}>
      {SCENES.map((s) => {
        const from = Math.max(0, Math.round((s.start - FADE) * fps));
        const dur = Math.round(s.end * fps) - from;
        return (
          <Sequence key={s.n} from={from} durationInFrames={dur} name={`Сцена ${s.n}`}>
            <SceneLayer scene={s} />
          </Sequence>
        );
      })}

      <Grain />
      <Vignette />

      {TITLES.map((t) => (
        <Sequence
          key={t.text}
          from={Math.round(t.start * fps)}
          durationInFrames={Math.round((t.end - t.start) * fps)}
          name={`Титр: ${t.text.split('\n')[0]}`}
        >
          <Title text={t.text} big={t.big} />
        </Sequence>
      ))}

      <Sequence from={Math.round(76.5 * fps)} name="Логотип">
        <EndCard />
      </Sequence>

      {MUSIC && <Audio src={staticFile(`audio/${MUSIC}`)} volume={0.45} />}
      {VOICE.map((v) => (
        <Sequence key={v.file} from={Math.round(v.start * fps)}>
          <Audio src={staticFile(`audio/${v.file}`)} />
        </Sequence>
      ))}
      {SFX.map((x) => (
        <Sequence key={x.file + x.start} from={Math.round(x.start * fps)}>
          <Audio src={staticFile(`audio/${x.file}`)} volume={x.volume ?? 1} />
        </Sequence>
      ))}
    </AbsoluteFill>
  );
};

// Сцена: готовый ИИ-клип или заглушка аниматика
const SceneLayer: React.FC<{scene: Scene}> = ({scene}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const opacity = scene.n === 1 ? 1 : interpolate(frame, [0, FADE * fps], [0, 1], {extrapolateRight: 'clamp'});
  return (
    <AbsoluteFill style={{opacity}}>
      {scene.clip ? <Video src={staticFile(`clips/${scene.clip}`)} /> : <Placeholder scene={scene} />}
    </AbsoluteFill>
  );
};

const Placeholder: React.FC<{scene: Scene}> = ({scene}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const look = STAGE_LOOK[scene.stage];
  const len = (scene.end - scene.start + FADE) * fps;
  const drift = interpolate(frame, [0, len], [0, 1], {extrapolateRight: 'clamp'});
  const smoky = scene.stage === 'dym' || scene.stage === 'pamyat' || scene.stage === 'final';
  return (
    <AbsoluteFill
      style={{
        background: `radial-gradient(ellipse at ${30 + drift * 40}% ${70 - drift * 20}%, ${look.to} 0%, ${look.from} 70%)`,
        scale: String(1.08 - drift * 0.06),
      }}
    >
      {/* мягкое «солнце» золотого часа */}
      <AbsoluteFill
        style={{
          background: `radial-gradient(circle at ${75 - drift * 10}% ${25 + drift * 8}%, rgba(255,196,120,0.35) 0%, rgba(255,196,120,0) 40%)`,
        }}
      />
      {smoky &&
        [0, 1, 2].map((i) => (
          <AbsoluteFill
            key={i}
            style={{
              background: `radial-gradient(ellipse at ${20 + i * 30 + Math.sin((frame + i * 40) / 50) * 8}% ${
                90 - ((frame * (0.25 + i * 0.1)) % 120)
              }%, rgba(190,185,200,0.22) 0%, rgba(190,185,200,0) 35%)`,
            }}
          />
        ))}
      {scene.stage !== 'final' && (
        <div
          style={{
            position: 'absolute',
            left: 96,
            top: 80,
            fontFamily,
            color: 'rgba(255,240,225,0.75)',
            fontSize: 30,
            letterSpacing: 2,
          }}
        >
          <div style={{fontSize: 22, opacity: 0.7, textTransform: 'uppercase', letterSpacing: 6}}>
            Аниматик · сцена {scene.n} · {look.label}
          </div>
          <div style={{marginTop: 10, maxWidth: 1100, fontStyle: 'italic'}}>{scene.what}</div>
        </div>
      )}
    </AbsoluteFill>
  );
};

// Плёночное зерно
const Grain: React.FC = () => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{mixBlendMode: 'overlay', opacity: 0.22, pointerEvents: 'none'}}>
      <svg width="100%" height="100%">
        <filter id="grain">
          <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" seed={frame % 12} />
          <feColorMatrix type="saturate" values="0" />
        </filter>
        <rect width="100%" height="100%" filter="url(#grain)" />
      </svg>
    </AbsoluteFill>
  );
};

const Vignette: React.FC = () => (
  <AbsoluteFill
    style={{background: 'radial-gradient(ellipse at center, rgba(0,0,0,0) 55%, rgba(0,0,0,0.55) 100%)'}}
  />
);

const Title: React.FC<{text: string; big?: boolean}> = ({text, big}) => {
  const frame = useCurrentFrame();
  const {fps, durationInFrames} = useVideoConfig();
  const inF = 0.9 * fps;
  const outF = 0.9 * fps;
  return (
    <AbsoluteFill
      style={{
        justifyContent: big ? 'center' : 'flex-end',
        alignItems: 'center',
        paddingBottom: big ? 0 : 130,
      }}
    >
      <div
        style={{
          fontFamily,
          fontWeight: 400,
          fontSize: big ? 84 : 60,
          lineHeight: 1.25,
          color: '#f6e7d4',
          textAlign: 'center',
          whiteSpace: 'pre-line',
          textShadow: '0 2px 24px rgba(0,0,0,0.6)',
          opacity: interpolate(frame, [0, inF, durationInFrames - outF, durationInFrames], [0, 1, 1, 0], {
            extrapolateLeft: 'clamp',
            extrapolateRight: 'clamp',
          }),
          translate: `0px ${interpolate(frame, [0, inF], [12, 0], {extrapolateRight: 'clamp', easing: ease})}px`,
        }}
      >
        {text}
      </div>
    </AbsoluteFill>
  );
};

// Финальная плашка: название аромата и логотип (логотип только из файла партнёра)
const EndCard: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const opacity = interpolate(frame, [0, 1.2 * fps], [0, 1], {extrapolateRight: 'clamp', easing: ease});
  return (
    <AbsoluteFill style={{justifyContent: 'center', alignItems: 'center', opacity}}>
      <div style={{fontFamily, color: '#f6e7d4', fontSize: 64, letterSpacing: 10, textTransform: 'uppercase'}}>
        Smoky Pomegranate
      </div>
      <div style={{marginTop: 48, height: 90, display: 'flex', alignItems: 'center'}}>
        {LOGO ? (
          <Img src={staticFile(`brand/${LOGO}`)} style={{height: 90}} />
        ) : (
          <div
            style={{
              fontFamily,
              color: 'rgba(246,231,212,0.6)',
              fontSize: 26,
              border: '1px dashed rgba(246,231,212,0.5)',
              padding: '18px 40px',
              letterSpacing: 4,
            }}
          >
            здесь логотип Tonka Perfumes (SVG из материалов)
          </div>
        )}
      </div>
    </AbsoluteFill>
  );
};
