// Таймлайн ролика. Источник: scenariy/01-scenariy-i-raskadrovka.md
// Когда клип сгенерирован, положи его в public/clips/ и впиши имя файла в поле clip.

export const FPS = 30;

export type Stage = 'prolog' | 'sok' | 'teplo' | 'dym' | 'pamyat' | 'final';

export type Scene = {
  n: number;
  start: number; // секунды
  end: number;
  stage: Stage;
  what: string; // что в кадре (для аниматика)
  clip?: string; // файл в public/clips/, например '04-sok.mp4'
};

export const SCENES: Scene[] = [
  {n: 1, start: 0, end: 6, stage: 'prolog', what: 'Рука чиркает спичкой, огонь освещает медь и край граната'},
  {n: 2, start: 6, end: 12, stage: 'sok', what: 'Снизу: ноги папы поднимаются по каменной лестнице, в руке свёрток'},
  {n: 3, start: 12, end: 18, stage: 'sok', what: 'Руки папы кладут огромный гранат на медный поднос, детские руки тянутся'},
  {n: 4, start: 18, end: 24, stage: 'sok', what: 'Макро: кожура трескается, зёрна блестят, капля сока'},
  {n: 5, start: 24, end: 30, stage: 'teplo', what: 'Детские ладони держат гранат у груди, он светится в окне'},
  {n: 6, start: 30, end: 36, stage: 'teplo', what: 'Чай льётся в армуду, сухая роза, специи, пар в луче'},
  {n: 7, start: 36, end: 42, stage: 'teplo', what: 'Пустой стул, пиджак папы на спинке, недопитый чай'},
  {n: 8, start: 42, end: 48, stage: 'dym', what: 'Вечерний двор, дым мангала поднимается через лозу'},
  {n: 9, start: 48, end: 53, stage: 'dym', what: 'Фактуры: кожаная сумка, нагретое дерево, камень'},
  {n: 10, start: 53, end: 58, stage: 'dym', what: 'Силуэты папы и девочки со спины уходят в дым'},
  {n: 11, start: 58, end: 64, stage: 'pamyat', what: 'Дым двора перетекает в дымок свечи. Наши дни'},
  {n: 12, start: 64, end: 72, stage: 'pamyat', what: 'Свеча Tonka горит рядом с гранатом, пустой стул напротив'},
  {n: 13, start: 72, end: 80, stage: 'final', what: 'Тёмно-винный фон, лёгкий дым'},
];

export const TOTAL_SECONDS = SCENES[SCENES.length - 1].end;

// Титры (дублируют голос за кадром). Время в секундах.
export const TITLES: {text: string; start: number; end: number; big?: boolean}[] = [
  {text: 'Папа всегда приносил домой\nсамый спелый гранат', start: 7, end: 13},
  {text: 'И в доме становилось тепло', start: 25, end: 31},
  {text: 'Дом остаётся с нами,\nдаже когда мы далеко', start: 65, end: 71},
  {text: 'Моему папе.\nОн родился в Баку', start: 72.5, end: 76.5, big: true},
];

// Цвета этапов из палитры брифа: для заглушек аниматика и подписей.
export const STAGE_LOOK: Record<Stage, {label: string; from: string; to: string}> = {
  prolog: {label: 'Пролог', from: '#140b0a', to: '#3a1d12'},
  sok: {label: '1. Сок граната', from: '#7a1420', to: '#c0392b'},
  teplo: {label: '2. Тепло дома', from: '#8a4a1c', to: '#c98a3c'},
  dym: {label: '3. Дым', from: '#3b3440', to: '#7d7480'},
  pamyat: {label: '4. Память', from: '#4a1a22', to: '#9c5a3c'},
  final: {label: 'Посвящение', from: '#1e0a0e', to: '#3d1219'},
};

// Голос за кадром: положи файлы в public/audio/ и впиши имена.
export const VOICE: {file: string; start: number}[] = [
  // {file: 'golos-1.mp3', start: 7},
  // {file: 'golos-2.mp3', start: 25},
  // {file: 'golos-3.mp3', start: 65},
];
export const MUSIC: string | null = null; // например 'muzyka.mp3'
export const SFX: {file: string; start: number; volume?: number}[] = [];

// Логотип Tonka (SVG из материалов партнёра) положи в public/brand/ и впиши имя.
export const LOGO: string | null = null; // например 'logo-white.svg'
