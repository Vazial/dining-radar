# KEN-24 監査報告（reviewer）

対象: ブランチ `Vazial/ken-24` の KEN-24 コミット（`33c5120` 契約・ADR、`564fa2b` 実装・L4）。
契約: ADR-0073 / ADR-0074 / `gathering-scheduling-browser-interface.yaml` 0.30.0 追補29 / `authentication-browser-interface.yaml` 0.4。
撮影画像（`ken-24-capture/*.png`）は日本語が□表示のため、文字内容は DOM とコードで確認した（390px の画像は日程タブに札が1枚だけ並ぶ形で、DOM 検証と一致）。

## 結論

**Critical 0件 / Major 0件 / Minor 6件。** 人間の承認に進めてよい。

実行して確かめたこと:
- 新規2本（`test_gth_schedule_tab_shows_only_the_decided_date_chip`、`test_b_gathering_dashboard_schedule_tab_shows_only_the_confirmed_date`）は緑。
- 変異検査: `gathering.js` の `card.hidden = true` を `false` に変えると、L4・UI不変条件・JS単体の3本とも赤になった（偽陽性ではない）。検査後に元へ戻した。
- 回帰: `test_gathering_scheduling_acceptance` + `test_authentication_acceptance` + `test_authentication` + `test_structure` の122本が緑。`ruff check` 緑。
- JS単体: `node --test tests/js_unit/*.test.js` 13本緑。

## 対訳表（コードから読んだ内容 → 契約）

| 対象 | コードが実際にやること | 契約 | 判定 |
|---|---|---|---|
| `assert_schedule_tab_shows_only_the_decided_date_chip(total)` | 日程タブを開き、`candidateDateList` が見えることを確認。札の総数が `total` であること、`data-confirmed` が `true` ちょうど1枚・他は `"false"` であること、**見えている札の id 集合 = 確定札の id 集合**を確認 | ADR-0073 決定1（見えるのは確定札1枚、他は DOM に残る、リスト自体は見える） | 合致 |
| `test_gth_schedule_tab_shows_only_the_decided_date_chip` | 3候補日の SELECTING_SHOP を作り、PC幅・スマホ幅それぞれで再読込して上記を検査 | 同上（専用シナリオの無い Must。追補28のテストと同じ扱い） | 合致 |
| `test_b_gathering_dashboard_schedule_tab_shows_only_the_confirmed_date` | UI で会を作り、1日確定→店1件→日程タブ。確定札は visible、他は hidden かつ `data-confirmed="false"` が残る | 同上 | 合致 |
| `gathering_schedule_tab_confirmed_only.test.js` | `gathering.js` の印付きブロックを `vm` で読み、偽の札に対して `hidden` が付くこと、`data-*` が変わらないことを検査 | 決定1（属性不変） | 合致（配線は上の2本が担保） |
| `authentication_browser.py` の変更 | サインイン成功の `present` から `auth-individual-account-guidance` と、その2属性の検査を外す | 認証契約 0.4（要求を外すだけ） | 合致 |
| `home.html` の変更 | ⓘ の `<span>` とその CSS を削除 | ADR-0074 決定1 | 合致 |
| `gathering.js` / `organizer.css` | 日程タブ描画時、`data-confirmed !== "true"` の札に `hidden` を付ける。`.gth-date[hidden]{display:none}` を足す（`.gth-date` が `inline-flex` で `hidden` を打ち消すため必要） | 決定1・2（SELECTING_SHOP のみ、`data-*` 不変、リスト自体は表示） | 合致 |

## レビューチェックリスト（5観点）

1. **過不足**: 決定1（1枚だけ見える・他は DOM に残る・属性不変・リスト自体は見える）は新規テストで押さえられている。決定3（店0件は不変）は日程タブの分岐が店0件の分岐より前にあるだけで、0件固有の新規テストは無い（変更もされていないので許容）。→ m2。
2. **Given の正当性**: 確定札は実際の確定操作（UI / ステップ）で作っている。`total_dates=3` を引数で渡し札数も検査しており、「札が減って1枚になった」の偽陽性を防いでいる。問題なし。
3. **Then の検証対象**: `is_visible()` で実際の可視性を見ている（`hidden` 属性の有無だけではない）。偽陽性なし（変異検査で確認済み）。ただし「属性不変」は `data-confirmed` しか見ていない。→ m1。
4. **失敗の握りつぶし**: 見つからなかった・0件のときに黙って通る経路は無い（`count()` 一致と `len(confirmed_ids)==1` を明示的に検査）。問題なし。
5. **暗黙の前提**: 札は SELECTING_SHOP の日程タブ描画でのみ `hidden` が付く（SCHEDULING / FINALIZED は別経路）。SCHEDULING は `assert_candidate_dates_are_small_chips` が3札すべてを `to_be_visible()` で検査し緑。FINALIZED は専用の可視性検査が無く、コード読みと既存テストの緑のみ。→ m3。

## 契約↔テスト対応

- 追補29の Must（見える1枚／他は DOM 残し）→ 上記3本で対応。孤児 step なし（新 step `schedule_tab_shows_only_the_decided_date_chip` は唯一の呼び出し元がある）。
- 認証契約 0.4: DSL・L3（`test_authentication.py`）から ⓘ 参照が消えている。コード・テスト・契約本文に `auth-individual-account-guidance` の取り残しは無い（残るのは ADR・履歴・コメントのみ。下の m4・m5）。
- 同義 step の重複なし。

## 指摘一覧

### Critical
なし。

### Major
なし。

### Minor
- **m1 属性不変の検証が薄い**: DSL・UI テストとも、隠した札で `data-confirmed` しか見ない。`data-going-count` 等の他の `data-*` が非表示化で変わらないことは、JS単体（偽の札）でも `data-confirmed` だけ。`hidden` 付与が他の属性を触らないコードなので実害は低いが、契約文言は「属性（`data-*`）は一切変えず」。隠された札の全 `data-*` を、隠す前後（または日程タブを開く前の他タブでの値）と比べる検査を足すとよい。
- **m2 店0件×日程タブは未検査**: 決定3は「店0件の表示は変更しない」。実装は店0件でも日程タブなら同じく1枚に畳む（店0件の既定タブは「店」で影響は薄い）。0件の日程タブで1枚になる／ならないは契約が決めておらず、テストも無い。判断材料として記録する。
- **m3 FINALIZED の札の可視性は専用検査なし**: SCHEDULING は小札検査で全札の可視性が押さえられているが、FINALIZED で全札が見える（または従来どおり）ことを直接検査するテストは無い。コード上は `hideUnconfirmedCandidateDates` が SELECTING_SHOP の日程タブ分岐からしか呼ばれないので退行は起きていない（関連する122本緑）。
- **m4 ⓘ が消えたこと自体を縛るテストが無い**: 契約は禁止 testId に足さない方針（ADR-0074 決定2）なので契約上は正しい。ただし `test_authentication.py` は `assertContains` を削っただけで `assertNotContains` が無く、ⓘ が復活しても何も赤くならない。L3 に `assertNotContains(shell, 'auth-individual-account-guidance')` 1行を足すとよい（契約変更は不要）。
- **m5 TDR-AUTH-02「認証情報の共有を求められない」がブラウザ境界で未観測**: `authentication-acceptance-review.md` の対訳表が「Not observable … carried by the scenario text only」と正直に書いており、人間裁定（ADR-0074）の帰結として受容できる。ただし同文書の判定は「Suitable」のままなので、承認者はこの1行が観測不能になった点を認識して承認すること。
- **m6 付随の取り残し**: (a) `projects/dining-radar/activeContext.md` 78–79行が「人間の判断待ち」に ⓘ と日程タブを残したまま（KEN-24 で決着済み。KEN-24 の記載も無い）。(b) `tests/js_unit` の実行コマンド `node --test tests/js_unit` はこの Node ではディレクトリ指定で失敗する（`*.test.js` の glob なら13本緑。既存のテストと同じヘッダの書き方で、今回の変更が原因ではない）。また `.github/workflows/ci-dining-radar.yml` に js_unit の実行が見当たらず、新規 JS 単体テストは CI では走らない可能性がある（判断できない: CI 定義の全体は読んでいない）。

## 判断できなかった点
- CI が `tests/js_unit` を実行するか（m6-b）。
- 撮影画像は日本語が□のため、文言・見た目の板との一致は判断していない（契約は文言を固定していない）。
