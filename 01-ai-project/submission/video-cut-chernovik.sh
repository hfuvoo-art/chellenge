#!/usr/bin/env bash
# Нарезка чернового видео (сценарий: scenarij-video-chernovik.md). НЕ запускать без согласия пользователя.
# Вход: записи OBS 13.11 (h264 1920x1080 60 fps, aac). Выход: draft/cuts/*.mp4 и draft/chernovik.mp4.
# Перекодирование (не -c copy): резка точная по кадру, а не по ключевым кадрам; все куски с одними параметрами для concat.
set -euo pipefail
SRC="/d/Obs/видео/всё"
OUT="$(dirname "$0")/draft"
mkdir -p "$OUT/cuts"
ENC=(-c:v libx264 -preset medium -crf 20 -r 30 -pix_fmt yuv420p -c:a aac -b:a 160k -ar 48000 -ac 2)

cut() { # cut <№> <файл без .mkv> <начало> <длит, с>
  ffmpeg -hide_banner -loglevel error -y -ss "$3" -i "$SRC/2026-11-13 $2.mkv" -t "$4" "${ENC[@]}" "$OUT/cuts/$1.mp4"
  echo "$1: $(ffprobe -v error -show_entries format=duration -of csv=p=0 "$OUT/cuts/$1.mp4") с"
}

cut 01 21-21-00 0:19 20   # запрос и точка 1
cut 02 21-25-55 0:12 20   # подтверждение и сбор
cut 03 21-36-17 1:40 25   # эскалация lite→pro
cut 04 21-48-19 0:10 20   # новая сессия: status, lock --verify
cut 05 21-48-19 1:15 15   # кеш: 0 вызовов
cut 06 21-51-56 5:08 25   # варианты и критик
cut 07 22-08-38 0:05 15   # точка 2
cut 08 22-08-38 2:10 20   # стратегия, export
cut 09 22-36-36 0:25 20   # точка 3 и итог

(cd "$OUT" && ls cuts/*.mp4 | sed "s|^|file '|; s|$|'|" > list.txt)  # пути относительно list.txt — так их читает concat
ffmpeg -hide_banner -loglevel error -y -f concat -safe 0 -i "$OUT/list.txt" -c copy "$OUT/chernovik.mp4"
echo "Итог: $(ffprobe -v error -show_entries format=duration -of csv=p=0 "$OUT/chernovik.mp4") с (должно быть ≤ 590)"

# Закадр (по желанию): записать голос в voice.m4a и наложить, приглушив звук записи:
# ffmpeg -i "$OUT/chernovik.mp4" -i voice.m4a -filter_complex "[0:a]volume=0.2[a0];[a0][1:a]amix=inputs=2:duration=first[a]" \
#   -map 0:v -map "[a]" -c:v copy -c:a aac -b:a 160k "$OUT/chernovik-voice.mp4"
# Кадр для проверки на ключи/ID каталога перед публикацией (1 кадр в 5 с):
# ffmpeg -i "$OUT/chernovik.mp4" -vf fps=1/5 "$OUT/check-%03d.png"
# ОБЯЗАТЕЛЬНО перед показом: в записи 13.11 в log.jsonl виден ID облачного каталога (gpt://<каталог>/…, 45–64 с и 140–163 с черновика).
# Блюр по шаблону (нужны opencv-python-headless, numpy; шаблон — кадр 150 с: ffmpeg -ss 150 -i chernovik.mp4 -frames:v 1 draft/f150.png):
# python blur-folder-id.py draft/chernovik.mp4 draft/f150.png draft/noaudio.mp4
# ffmpeg -i draft/noaudio.mp4 -i draft/chernovik.mp4 -map 0:v -map 1:a -c:v libx264 -crf 20 -pix_fmt yuv420p -c:a copy draft/chernovik-blur.mp4
