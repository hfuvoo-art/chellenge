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
  clipSec?: number; // длина клипа в секундах: короткий клип замедляем до длины сцены
  clipVolume?: number; // громкость родного звука клипа (Kling генерирует его вместе с видео)
};

export const SCENES: Scene[] = [
  // Финальная версия 22.11: 11 ИИ-клипов, ~68 с. Сцена 9 (фактуры) убрана ради сроков.
  {n: 1, start: 0, end: 5, stage: 'prolog', what: 'Рука чиркает спичкой, огонь освещает медь и край граната', clip: 's01.mp4', clipSec: 3},
  {n: 2, start: 5, end: 10, stage: 'sok', what: 'Снизу: ноги папы поднимаются по каменной лестнице, в руке свёрток', clip: 's02.mp4', clipSec: 3},
  {n: 3, start: 10, end: 15, stage: 'sok', what: 'Руки папы кладут огромный гранат на медный поднос, детские руки тянутся', clip: 's03.mp4'},
  {n: 4, start: 15, end: 20, stage: 'sok', what: 'Макро: кожура трескается, зёрна блестят, капля сока', clip: 's04.mp4'},
  {n: 5, start: 20, end: 25, stage: 'teplo', what: 'Детские ладони держат гранат у груди, он светится в окне', clip: 's05.mp4'},
  {n: 6, start: 25, end: 30, stage: 'teplo', what: 'Чай льётся в армуду, сухая роза, специи, пар в луче', clip: 's06.mp4'},
  {n: 7, start: 30, end: 35, stage: 'teplo', what: 'Пустой стул, пиджак папы на спинке, недопитый чай', clip: 's07.mp4', clipSec: 3},
  {n: 8, start: 35, end: 40, stage: 'dym', what: 'Вечерний двор, дым мангала поднимается через лозу', clip: 's08.mp4'},
  {n: 10, start: 40, end: 45, stage: 'dym', what: 'Силуэты папы и девочки со спины уходят в дым', clip: 's10.mp4'},
  {n: 11, start: 45, end: 50, stage: 'pamyat', what: 'Дым двора перетекает в дымок свечи. Наши дни', clip: 's11.mp4'},
  {n: 12, start: 50, end: 60, stage: 'pamyat', what: 'Свеча Tonka горит рядом с гранатом, пустой стул напротив', clip: 's12.mp4'},
  {n: 13, start: 60, end: 68, stage: 'final', what: 'Тёмно-винный фон, лёгкий дым'},
];

export const TOTAL_SECONDS = SCENES[SCENES.length - 1].end;

// Титры (дублируют голос за кадром). Время в секундах.
export const TITLES: {text: string; start: number; end: number; big?: boolean}[] = [
  {text: 'Папа всегда приносил домой\nсамый спелый гранат', start: 5.5, end: 10.5},
  {text: 'И в доме становилось тепло', start: 21, end: 26},
  {text: 'Дом остаётся с нами,\nдаже когда мы далеко', start: 52, end: 58},
  {text: 'Моему папе.\nОн родился в Баку', start: 60.5, end: 64.5, big: true},
];

// Когда появляется логотип и название аромата (секунды)
export const ENDCARD_START = 64.5;

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
// Голос, музыка и звуки из ElevenLabs. Файлы в public/audio/; отсутствующие пропускаются.
export const VOICE: {file: string; start: number}[] = [
  {file: 'golos-1.mp3', start: 5.5},
  {file: 'golos-2.mp3', start: 21},
  {file: 'golos-3.mp3', start: 52},
];
export const MUSIC: string | null = 'muzyka.mp3';
export const SFX: {file: string; start: number; volume?: number}[] = [
  {file: 'sfx-spichka.mp3', start: 0.5},
  {file: 'sfx-shagi.mp3', start: 5, volume: 0.7},
  {file: 'sfx-bumaga.mp3', start: 10.5, volume: 0.7},
  {file: 'sfx-granat.mp3', start: 15.5},
  {file: 'sfx-chasy.mp3', start: 20, volume: 0.4},
  {file: 'sfx-chay.mp3', start: 25, volume: 0.8},
  {file: 'sfx-stul.mp3', start: 30.5, volume: 0.6},
  {file: 'sfx-ugli.mp3', start: 35, volume: 0.7},
  {file: 'sfx-ugli.mp3', start: 40, volume: 0.5},
  {file: 'sfx-fitil.mp3', start: 46, volume: 0.8},
  {file: 'sfx-fitil.mp3', start: 52, volume: 0.6},
];
export const LOGO: string | null = 'logo-white.svg'; // например 'logo-white.svg'
