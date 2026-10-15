# Dining Radar の画面撮影

ローカルの合成データで、スマホ・iPad 縦横・PC の全画面を撮影する。

```bash
cd projects/dining-radar
DINING_RADAR_CAPTURE_DIR=/tmp/dining-radar-capture \
DJANGO_SECRET_KEY=synthetic-ci-verification-only \
DJANGO_ALLOWED_HOSTS=example.invalid \
.venv/bin/python -m pytest tests/ui_invariants/test_zz_capture_states.py -q
```

`DINING_RADAR_CAPTURE_DIR` 配下の PNG と JSON を画面サイズごとに開いて確認する。撮影サイズは 375px、820×1180px、1180×820px、1440px で、撮影データには複数の会、長い名称、長い店名、多人数、各進行局面を含める。
