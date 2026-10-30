---
name: "remotion-montage"
description: "Монтаж видео кодом в Remotion: сборка ИИ-клипов на таймлайне, титры, субтитры, музыка, голос, переходы, рендер в MP4. Для ролика MGIMO×AI Challenge и любого видео в Remotion."
---

# Монтаж в Remotion

Сжатая версия официальных Remotion Agent Skills (remotion-dev/skills). Если чего-то нет здесь, читай актуальную документацию: `https://www.remotion.dev/docs/<тема>.md` (например `/docs/sequence.md`, `/docs/transitions.md`, `/docs/captions/caption.md`, `/docs/cli/render.md`).

## Не ломай правки пользователя
Пользователь может менять код сам. Если видишь неожиданное изменение, не перезаписывай его, считай намеренным или спроси.

## Новый проект
Нужны Node.js и Git. Посмотри содержимое папки (включая скрытые файлы).
- Пустая папка: `npx create-video@latest --yes --blank --no-tailwind .` затем `npm i`
- Непустая: `npx create-video@latest --yes --blank --no-tailwind my-video`, `cd my-video`, `npm i`

Сразу после установки запусти превью и держи его открытым, чтобы пользователь видел изменения: `npx remotion studio` (или `--no-open` и открой напечатанный URL; конкретная композиция: `http://localhost:3000/<id>`).

Пакеты ставь только так, чтобы версии совпали: `npx remotion add @remotion/media` (то же для `@remotion/*`, `zod`, `mediabunny`).

## Правила разметки
- Анимации только через `useCurrentFrame()` + `interpolate()`; CSS `transition`/`animation` и анимации Tailwind при рендере не работают.
- `fps` бери из `useVideoConfig()`, тайминги пиши прямо в JSX: `from={2 * fps}`, `durationInFrames={5 * fps}`, `trimBefore={4 * fps}`.
- `useCurrentFrame()` держи в самом маленьком компоненте (титры, оверлеи, громкость отдельно), иначе всё перерисовывается каждый кадр.
- `interpolate` пиши инлайн в `style`, с `extrapolateLeft/Right: 'clamp'`; используй свойства `scale`, `translate`, `rotate`, а не строку `transform`. Для `scale` добавляй `output: 'perceptual-scale'`. Плавность: `Easing.bezier(0.16, 1, 0.3, 1)` или `Easing.spring({damping: 200})`.
- Обёртки `Interactive.Div` с `name` позволяют править элементы прямо в Studio.

## Ассеты и медиа
- Файлы кладём в `public/`, ссылаемся через `staticFile("clip1.mp4")`.
- Видео и аудио: `<Video>` и `<Audio>` из `@remotion/media`; картинки: `<CanvasImage>` из `remotion`; GIF/WebP: `<AnimatedImage>`.
- Обрезка и громкость: пропсы `trimBefore`, `trimAfter`, `volume` (можно функцией от кадра для fade), `playbackRate`.

## Таймлайн из клипов (главный сценарий для ИИ-ролика)
- Каждый клип, который монтируется отдельно, это свой JSX-узел в своём `<Sequence from={...} durationInFrames={...}>`.
- Подряд идущие сцены: `<Series>` / `<Series.Sequence>`; с переходами: `<TransitionSeries>` из `@remotion/transitions` (`fade()`, `slide()`, `wipe()` + `linearTiming({durationInFrames})` или `springTiming()`).
- Музыка отдельной дорожкой `<Audio>` на всю длину, приглушай под голос через `volume`.
- Длительность композиции считай от суммы клипов; если она зависит от файлов, используй `calculateMetadata`.
- Формат задаётся в `<Composition width height fps durationInFrames>`: 1920×1080 (16:9) или 1080×1920 (9:16), 30 fps.

## Текст и шрифты
- Шрифты через `@remotion/google-fonts` (`loadFont()` из нужного шрифта), с кириллицей проверяй `subsets: ['cyrillic']`.
- Крупный текст: видео смотрят издалека и с телефона, минимум ~48px для 1080p, держи безопасные поля по краям.

## Субтитры
- Формат: массив `Caption` из `@remotion/captions` (`text`, `startMs`, `endMs`, `timestampMs`, `confidence`).
- Из `.srt`: `parseSrt()`; группировка в «страницы»: `createTikTokStyleCaptions()`; транскрипция голоса: `@remotion/install-whisper-cpp` (см. документацию).

## Эффекты
`@remotion/effects` прямо в проп `effects` у `<Video>`, `<Img>`, `<CanvasImage>`: `vignette()`, `colorCorrection()`, `lut()` для общего цветокора, `blur()`, `glow()`, `lightLeak()`, `noise()`, `chromaticAberration()` и др. Для обычного HTML оберни в `<HtmlInCanvas>`.

## Проверка и рендер
- Проверяй в Studio всю композицию: слои, точки склейки, синхрон звука.
- Отдельные кадры картинками: `npx remotion render <id> out/frames --frames=0,30,90 --image-format=png`.
- Рендер только когда пользователь явно просит («рендери», «дай MP4»): `npx remotion render <id> out/video.mp4` (по умолчанию H.264). Рендер идёт локально на компьютере пользователя.

## Для конкурса
Перед монтажом возьми сценарий, раскадровку и монтажный лист из скила ai-video-pipeline. В описании работы перечисли все нейросети и то, что монтаж сделан кодом в Remotion с Claude: это поднимает критерий «масштаб использования нейротехнологий».