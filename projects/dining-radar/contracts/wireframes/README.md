# KEN-68 採用板

このディレクトリは、KEN-68 で合意した案 C の板を CI で照合するための固定入力です。

- 出典: [Claude artifact UVcB1TqUYVxFaWuKP46j4u](https://claude.ai/artifact/UVcB1TqUYVxFaWuKP46j4u)
- 取得日: 2026-10-12
- `project/`: 板の静的 HTML
- `png/`: 板の参照画像
- `geometry.json`: `tools/generate_wireframe_geometry.py` で板 HTML を Playwright 描画して生成した期待矩形

再生成:

```sh
python tools/generate_wireframe_geometry.py
```

照合テストは `tests/ui_invariants/test_wireframe_conformance.py` です。板 HTML の対応要素は同テストと生成スクリプトの `AREA_SELECTORS` に明示し、矩形はビューポートに対する 0..1 の比率で保存します。板の意図的な差分は仕様の `notes` に理由を残します。

左右比較画像は、キャプチャ先を指定して次のコマンドで生成できます。画像処理ライブラリがある環境では `compare/` に PNG を出力します。

```sh
python tools/generate_wireframe_geometry.py --compare-dir /tmp/claude-1000/capture68-fixed
```
