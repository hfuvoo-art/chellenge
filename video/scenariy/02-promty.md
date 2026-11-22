# Библия стиля и промпты по кадрам

Промпты на английском: генераторы картинок и видео понимают его лучше. Порядок работы на каждый кадр: сначала картинка-референс, потом видео из неё (image-to-video). Так стиль и предметы держатся стабильнее.

## Библия стиля

Эти куски вставляем в каждый промпт без изменений.

**STYLE** (в конец каждого промпта картинки):
> shot on 35mm film, Kodak Portra 400, soft film grain, golden hour, low warm sun, long soft shadows, shallow depth of field, palette of pomegranate red, deep wine, copper, ochre, sandstone, bluish-grey smoke, intimate and quiet mood, no text, no logos, no flags

**PAPA** (папа, всегда без лица):
> a man's large weathered hands, olive skin, a thin silver wedding ring, sleeves of a worn brown wool jacket; his face is never visible, out of frame or seen only from behind

**CHILD** (девочка 5 лет, без лица):
> small hands of a five-year-old girl, a faded red cotton dress with a tiny white pattern; seen from behind or only hands, face never visible

**HOME** (дом в старом Баку, не туристический):
> an old courtyard house in Baku, warm sandstone walls, wooden balcony with carved railings, grapevine over the courtyard, worn stone steps, copper trays and pots, linen cloth, lived-in and modest, not touristic

**POMEGRANATE** (главный герой, один и тот же во всех сценах):
> one very large heavy ripe pomegranate, deep red skin with a natural crack at the base revealing glossy ruby seeds

**Правила стиля**
- Один и тот же референс граната, рук папы и платья девочки подаём во все кадры как image reference (character / object reference).
- Камера на высоте ребёнка (около 1 метра) во всех сценах прошлого.
- Наши дни отличаются только светом: тот же золотой тон, но холоднее и тише. Медь и гранат те же.
- Негатив (где можно): faces, text, watermark, flag, emblem, extra fingers, plastic look, oversaturated.

## Продукт

Генерируем строго из фото партнёра. Фото свечи подаём как референс (Flux Kontext, Nano Banana / Gemini Image или аналог с редактированием по фото), просим поставить её в нашу сцену без изменений формы и цвета. Надпись на свече и логотип не генерируем: если генератор исказит этикетку, закрываем её чистой версией при монтаже. Потом image-to-video с минимальным движением камеры, чтобы продукт не «поплыл».

## Кадры

### 1. Спичка (0–6 с)
- Картинка: `extreme close-up macro, a woman's hand striking a match in a dark quiet room, the small flame lights the edge of a copper tray and the curve of a red pomegranate, deep darkness around` + STYLE
- Видео: `the match ignites, flame flickers, warm light slowly grows on the copper, static macro camera`

### 2. Лестница (6–12 с)
- Картинка: `low camera at child height looking up worn stone steps of` HOME `, a man's legs in old leather shoes climbing the steps, in his hand a paper bundle, golden evening light through the vine` + STYLE
- Видео: `the man slowly climbs the stairs away from camera, camera tilts up gently following him, swallows cross the sky, light flickers through grape leaves`

### 3. Поднос (12–18 с)
- Картинка: `top-down medium shot,` PAPA `placing` POMEGRANATE `on a hammered copper tray on a wooden table, the` CHILD `reaches in from the bottom of the frame` + STYLE
- Видео: `the hands set the pomegranate down and withdraw, the small hands reach toward it, slow push-in`

### 4. Сок (18–24 с)
- Картинка: `extreme macro of` POMEGRANATE `, the crack opens, ruby seeds glisten, a single drop of juice runs down the skin, backlit by warm sun` + STYLE
- Видео: `the crack slowly widens, seeds glisten, one drop of juice slides down and falls, very slow camera drift`
- Вариант Б: `slow motion, pomegranate seeds tumble onto copper, juice splashes in sunlight`

### 5. Гранат в ладонях (24–30 с)
- Картинка: `close-up,` CHILD `holding` POMEGRANATE `against her chest with both hands, warm window light makes the fruit glow` + STYLE
- Видео: `the small hands gently turn the pomegranate, breathing motion, handheld subtle movement, dust in the light`

### 6. Чай (30–36 с)
- Картинка: `side view of a kitchen table in` HOME `, dark black tea being poured from a copper teapot into a pear-shaped armudu glass, a saucer with dried rose buds, cardamom and cinnamon on linen cloth, steam glowing in a sunbeam` + STYLE
- Видео: `tea pours into the glass, steam curls up through the sunbeam, slow lateral dolly`

### 7. Пустой стул (36–42 с)
- Картинка: `an empty old wooden chair, a man's worn brown wool jacket hanging on its back, a half-finished glass of tea on the table, late golden light, the room feels like someone just left` + STYLE
- Видео: `static camera, sunlight slowly moves across the chair, steam from the tea thins out`

### 8. Дым во дворе (42–48 с)
- Картинка: `dusk in the courtyard of` HOME `, soft smoke from a small charcoal grill rises through the grapevine, warm stone walls glowing, copper reflections, first lights in the windows` + STYLE
- Видео: `smoke drifts slowly upward through leaves, camera tilts up following the smoke, embers glow`

### 9. Фактуры (48–53 с)
- Картинка: `macro textures: an old leather satchel on a wooden bench, warm worn wood grain, rough sandstone wall, soft smoke passing` + STYLE
- Видео: `slow macro slide along the leather and wood, smoke passes through the frame`

### 10. Уходят в дым (53–58 с)
- Картинка: `wide shot from behind, silhouettes of a man and a small girl in a red dress walking hand in hand into the depth of the courtyard, soft smoke and dusk light, faces not visible` + STYLE
- Видео: `the two silhouettes walk slowly away, smoke thickens and fills the frame, static camera`

### 11. Дым становится свечой (58–64 с)
- Картинка: `macro, a thin wisp of smoke rising from a freshly lit candle in a quiet modern room, beside it a copper tray with a split pomegranate, calm muted golden light` + STYLE
- Видео: `the smoke wisp curls upward matching the shape of the previous shot, static macro`
- Монтаж: совмещаем форму дыма из кадра 10 и кадра 11 через наплыв.

### 12. Свеча Tonka (64–72 с)
- Картинка (с фото продукта как референсом): `the exact candle from the reference photo, same shape, same colors, burning on an old wooden table next to` POMEGRANATE `split open, a glass of dark tea, a woman's hand gently touches the pomegranate, an empty wooden chair across the table, quiet evening light` + STYLE
- Видео: `the candle flame flickers softly, thin smoke rises, the hand rests on the fruit, very slow pull-back, the candle stays perfectly still and unchanged`

### 13. Финал (72–80 с)
- Картинка: `deep wine-red background with soft drifting smoke, subtle film grain, empty space for text` + STYLE
- Видео: `smoke drifts slowly, almost still`
- Титры и логотип накладываем в Remotion.

## Звук

**Голос** (ElevenLabs или аналог, русский, тихий тёплый женский голос, тариф с коммерческой лицензией). Текст с паузами:
1. «Папа… всегда приносил домой… самый спелый гранат.»
2. «И в доме… становилось тепло.»
3. «Дом остаётся с нами… даже когда мы далеко.»

**Музыка** (Suno / Udio на платном тарифе или ElevenLabs Music):
> slow intimate instrumental, 60 BPM, solo tar and soft kamancha over warm cello drone, sparse piano notes, restrained, nostalgic, warm, no drums, no vocals, gentle swell around 0:45, fades to silence at 1:05, avoid ethnic cliches

**Живые звуки** (ElevenLabs Sound Effects или аналог): чирк спички; шаги по каменным ступеням; ласточки в вечернем небе; шорох бумажного свёртка; звон медного подноса; хруст кожуры граната; капля сока; детское дыхание; тикающие часы; чай льётся в стеклянный стакан; ложечка о стекло; кипящий чайник; скрип деревянного стула; треск углей; сверчки; лёгкий ветер в листьях; потрескивание фитиля свечи.

## Для описания работы

На каждом шаге сохраняем скриншоты: промпт, удачную и неудачную генерацию, тариф сервиса. Это прямо требуется в описании и поднимает критерий «масштаб нейротехнологий».
