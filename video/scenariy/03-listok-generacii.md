# Листок генерации ИИ-ролика (22.11, сдача сегодня)

Ролик ~68 секунд, 11 клипов. Для каждой сцены: **сначала картинка, потом видео из этой картинки** (режим «Image to Video»). Формат везде **16:9**, видео **5 секунд** (сцена 12: **10 секунд**). Готовый клип называй как в колонке «Файл» и кидай сюда в чат (или в Google Диск, ссылку в чат).

Скриншоты для описания (обязательно по брифу): на каждой сцене один скрин с промптом и результатом, плюс хотя бы 2 неудачные генерации, плюс скрин тарифа каждого сервиса.

## 0. Сначала, 10 минут: опорные картинки

Чтобы герои и гранат были одинаковыми во всех кадрах, сделай три картинки и дальше подавай их как референс (Reference / Elements / Character):

- **ref-granat:** `one very large heavy ripe pomegranate, deep red skin with a natural crack at the base revealing glossy ruby seeds, on a hammered copper tray, golden hour light, 35mm film, Kodak Portra 400, soft film grain`
- **ref-papa:** `a man's large weathered hands, olive skin, a thin silver wedding ring, sleeves of a worn brown wool jacket, holding a paper bundle, face not visible, golden hour, 35mm film, soft grain`
- **ref-devochka:** `small hands of a five-year-old girl, a faded red cotton dress with a tiny white pattern, seen from behind, face not visible, golden hour, 35mm film, soft grain`

## Хвост для каждой картинки (STYLE)

Добавляй в конец каждого промпта картинки:

```
, shot on 35mm film, Kodak Portra 400, soft film grain, golden hour, low warm sun, long soft shadows, shallow depth of field, palette of pomegranate red, deep wine, copper, ochre, sandstone, bluish-grey smoke, intimate and quiet mood, no text, no logos, no flags
```

Негатив, если есть поле: `faces, text, watermark, flag, emblem, extra fingers, plastic look, oversaturated`

## Сцены

| Файл | Этап | Картинка (+ STYLE) | Видео (движение) |
|---|---|---|---|
| s01.mp4 | Пролог | `extreme close-up macro, a woman's hand striking a match in a dark quiet room, the small flame lights the edge of a copper tray and the curve of a red pomegranate, deep darkness around` | `the match ignites, flame flickers, warm light slowly grows on the copper, static macro camera` |
| s02.mp4 | Сок | `low camera at child height looking up worn stone steps of an old courtyard house in Baku, warm sandstone walls, wooden balcony with carved railings, grapevine, a man's legs in old leather shoes climbing the steps, in his hand a paper bundle, golden evening light through the vine` | `the man slowly climbs the stairs away from camera, camera tilts up gently, light flickers through grape leaves` |
| s03.mp4 | Сок | `top-down medium shot, a man's weathered hands with a silver ring placing one very large ripe cracked pomegranate on a hammered copper tray on a wooden table, small hands of a little girl in a red dress reach in from the bottom of the frame` (реф: гранат, папа, девочка) | `the hands set the pomegranate down and withdraw, the small hands reach toward it, slow push-in` |
| s04.mp4 | Сок | `extreme macro of a very large ripe pomegranate, the crack opens, ruby seeds glisten, a single drop of juice runs down the skin, backlit by warm sun` (реф: гранат) | `the crack slowly widens, seeds glisten, one drop of juice slides down and falls, very slow camera drift` |
| s05.mp4 | Тепло | `close-up, small hands of a five-year-old girl in a faded red dress holding a very large pomegranate against her chest, warm window light makes the fruit glow` (реф: гранат, девочка) | `the small hands gently turn the pomegranate, subtle handheld movement, dust in the light` |
| s06.mp4 | Тепло | `side view of a modest kitchen table in an old Baku house, dark black tea poured from a copper teapot into a pear-shaped armudu glass, a saucer with dried rose buds, cardamom and cinnamon on linen cloth, steam glowing in a sunbeam` | `tea pours into the glass, steam curls up through the sunbeam, slow lateral dolly` |
| s07.mp4 | Тепло | `an empty old wooden chair, a man's worn brown wool jacket hanging on its back, a half-finished glass of tea on the table, late golden light, the room feels like someone just left` | `static camera, sunlight slowly moves across the chair, steam from the tea thins out` |
| s08.mp4 | Дым | `dusk in the courtyard of an old Baku house, soft smoke from a small charcoal grill rises through the grapevine, warm sandstone walls glowing, copper reflections, first lights in the windows` | `smoke drifts slowly upward through leaves, camera tilts up following the smoke, embers glow` |
| s10.mp4 | Дым | `wide shot from behind, silhouettes of a man in a brown jacket and a small girl in a red dress walking hand in hand into the depth of the courtyard, soft smoke and dusk light, faces not visible` | `the two silhouettes walk slowly away, smoke thickens and fills the frame, static camera` |
| s11.mp4 | Память | `macro, a thin wisp of smoke rising from a freshly lit candle in a quiet modern room, beside it a copper tray with a split pomegranate, calm muted golden light` | `the smoke wisp curls slowly upward, static macro` |
| s12.mp4 (10 с) | Память | **Подай фото свечи 220 мл из материалов как референс.** `the exact candle from the reference photo: deep wine-red faceted glass jar with diamond pattern, brushed gold label, the matching ribbed red glass lid removed and resting beside the jar; the candle is lit, a small flame inside the jar, same shape, same colors, on an old wooden table next to a large split pomegranate, a glass of dark tea, a woman's hand gently touches the pomegranate, an empty wooden chair across the table, quiet evening light` | `the candle flame flickers softly, thin smoke rises, very slow pull-back, the candle stays perfectly still and unchanged` |

Сцена 12 самая важная для баллов: свеча должна совпасть с фото (фото лежит в [materialy](/mnt/project-files/rolik/materialy/), файл «Арома свеча 220 мл.jpg»). У свечи есть крышка: в промпте сказано, что крышка снята и лежит рядом, иначе свечу не зажечь. Если этикетка поплыла, не страшно, закрою её чистой при монтаже. Если поплыла форма или цвет, перегенерируй.

Финальный титр (сцена 13) и логотип делаю я в монтаже, генерировать не надо.

## Звук: ElevenLabs, тариф Starter (там коммерческая лицензия)

**Голос** (Text to Speech, русский, тихий тёплый женский голос, без дикторской подачи). Три отдельных файла:
- golos-1.mp3: «Папа… всегда приносил домой… самый спелый гранат.»
- golos-2.mp3: «И в доме… становилось тепло.»
- golos-3.mp3: «Дом остаётся с нами… даже когда мы далеко.»

**Музыка** (Music), muzyka.mp3, 70 секунд:
```
slow intimate instrumental, 60 BPM, solo tar and soft kamancha over warm cello drone, sparse piano notes, restrained, nostalgic, warm, no drums, no vocals, gentle swell around 0:35, fades to silence at 1:05
```

**Живые звуки** (Sound Effects), по файлу на строку, 3–5 секунд:
sfx-spichka (чирк спички), sfx-shagi (шаги по каменным ступеням, ласточки), sfx-bumaga (шорох бумажного свёртка и звон медного подноса), sfx-granat (хруст кожуры граната, капля), sfx-chasy (тикающие часы в тихой комнате), sfx-chay (чай льётся в стеклянный стакан, ложечка о стекло), sfx-stul (скрип деревянного стула, затихающие шаги), sfx-ugli (треск углей, сверчки, ветер в листьях), sfx-fitil (потрескивание фитиля свечи).

## Что ещё прислать

- Логотип Tonka из кабинета в SVG (белый) и фото свечи 220 мл.
- Скриншоты тарифов Kling/Higgsfield и ElevenLabs.
