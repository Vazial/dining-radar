---
id: 0079
scope: project/dining-radar
status: 承認済み
date: 2026-10-11
approved_by: "人間裁定（KEN-58 の決定9点と、聞く点への回答。人間が調整役とのチャットで1点ずつ合意し、調整役 ken-18-03 が2026-10-11に伝達）。ADR の起草・承認済み化は担当に委任。決定3の暫定の解除（決定5〜9）も人間の言葉「いったん①で進める。あとで実物を見て確認」を ken-18-03 が2026-10-11に伝達"
supersedes: []
superseded_by: null
relates_to: [ADR-0063, ADR-0069, ADR-0072, ADR-0073, ADR-0075, ADR-0076, ADR-0078]
---

# ADR-0079: 会の画面を縦の3手順（日程・店・決まり）にし、PCは地図を右に常に出す

> **承認者向けサマリ**: KEN-58 の人間の決定 3（**確定**。当初は暫定だったが、人間が「いったん①で進める。あとで実物を見て確認」と言い、確定扱いにした。2026-10-11 追補37）と 4（**今回は触らない**）。会の画面（幹事画面）は同じ1画面が3局面
> （日程を聞き中・店を選び中・決まった）で、いまは局面ごとに並びが違う（店を選び中は 店／日程／回答／リンク のタブ、
> 地図は店の一覧の隣、決まった画面は地図が見出しの下から端まで）。**決定1**: どの局面でも縦に「日程・店・決まり」の3手順を並べ、
> 済んだ手順は1行に畳む。**決定2**: PC は右の列に地図を常に出す。スマホは「店」の手順の中に地図を置き、決まったあとも残す。
> **決定3**: 日が決まる前に店を入れられるか（案B）は後のスコープ。今回の契約は今のまま（局面の流れ・日ごとの開いている店の数）。
> **契約が一番動くのは地図の位置**（確認事項Q1）。決定1・2は当初の追補33では新しい節の追加だけにして既存のタブや地図の要素を消さなかったが、
> 決定5〜9（追補37）でそれらを廃止・移動として書き直した。

## 文脈

### 検証の申告

実際に `Read` したもの: `gathering-scheduling-browser-interface.yaml`（0.32.0）の `organizerDashboard`（`schedulingLayout`・
`shopSelectionPanel`・`finalizedSummary`・`headingBar`・`confirmDate`・`tentativeSelectionAndPreview`）、ADR-0069・0072・0073・0075・0076
の要旨（契約中の引用から）、キャンバスの付箋と GC・GA・GB 各ページの文字。キャンバスは公開版 `1791707424-0a91`（依頼文の「版67」との対応は未確認）。
確認していないもの: 実装コード、ADR-0063 の全文（契約中の引用だけ読んだ）。

### 現状

- 同じ画面が3局面。SCHEDULING は ADR-0072・0076 で板 Q5-a に戻した（日を決める表→決めるボタン→候補日→リンク）。SELECTING_SHOP は
  タブ4つ（`shopTab`・`scheduleTab`・`answersTab`・`linksTab`、ADR-0073 で日程タブは決まった日1枚に畳む）。FINALIZED は
  `finalizedSummary`（見出しの下から地図いっぱい、ADR-0063 決定2・ADR-0069 決定4）。
- キャンバスの案C（暫定確定）は、局面をまたいで同じ3手順の縦の並びにし、PC は右列に地図を常設する。

## 決定

1. **3手順の縦の並び**（`organizerDashboard.stepFlow`、表示と DOM の順は 日程→店→決まり）。各手順は `gathering-step`（新設、3個）で、
   `data-step`（SCHEDULE／SHOP／FINAL）と `data-step-state`（done／current／upcoming）を持つ。局面との対応は表のとおり。

   | 局面 | 日程 | 店 | 決まり |
   |---|---|---|---|
   | SCHEDULING | current | upcoming | upcoming |
   | SELECTING_SHOP | done | current | upcoming |
   | FINALIZED | done | done | current |

   `done` の手順は**画面で見えるのが1行だけ**（日程なら決まった日、店なら決まった店）。詳しい中身（回答の表など）は、その1行にある
   入口を押したときだけ見える。ADR-0073 の「決まった日1枚だけ見える」はこの1行に読み替える。`upcoming` の手順は1行の案内だけ。
2. **地図の置き場所**（`organizerDashboard.mapPlacement`）。**PC**: 右の列に常に出す（3局面とも。日程を聞き中は検索基点のマーカーだけ）。
   **スマホ**: 「店」の手順の中に置き、FINALIZED では「決まり」の手順の中に残す。日程を聞き中のスマホには出さない。
   これで次を**覆す**: ADR-0063 決定2・ADR-0069 決定4（決まった画面で見出しの下から端まで埋める）のうち PC の部分、
   および「店を選び中は地図が店の一覧の隣」という配置。testId（`gathering-shortlisted-shop-map` ほか、`gathering-decision-shop-map` ほか）は
   変えない。**位置は ADR-0066 決定2により Must**（幾何条件 SF-1〜SF-4）。
3. **残すもの**: 上部バー（ADR-0075 決定1）、戻り道と会の名前の並び、`confirmDate`（日の手順の中、表の下。ADR-0072 決定3）、
   確定の確認ダイアログ、会の削除は無変更。局面の3値と `gathering-phase-indicator` の出現規則も無変更。
4. **決める点4（日の前に店を入れる案B）は今回のスコープ外**。契約・API は触らない。後のスコープの論点は
   `contracts/KEN-58-PROPOSAL.md` の「後のスコープ」にメモした。

## 確認事項（起草時の選択肢。回答は末尾の表）

- **Q1 決まったあとの PC の地図**。キャンバスは決まった PC の案C を描いておらず、参考ページの付箋は「決まった PC は案A のまま」、
  決定文は「PC は右に地図を常に出す」で、読み方が割れる。案: **(A)** 右の列に出す（決定文どおり。推奨。ただし板が無いので designer に
  決まった PC を描いてもらう）。**(B)** 案A（見出しの下から端まで）のまま（ADR-0069 決定4 を生かす。「常に」とは食い違う）。
- **Q2 日程を聞き中の PC に地図を出すか**。出すと、店の情報を一切出さない決まり（TDR-GTH-08・09: 日程の段階では件数だけ）を保ったまま
  検索基点だけを置く形になる。案: **(A)** 出す（案Cの絵どおり。推奨）。**(B)** 出さず右列を空けておく。
- **Q3 タブの行き先**。店を選び中の 回答・リンク のタブ（`answersTab`・`linksTab`）が、案Cの絵には無い。案: **(A)** 「日程」の手順の1行に
  「回答の表」の入口、リンクは「日程」の手順の中の節に移す（推奨）。**(B)** 手順とは別に小さなタブを残す。**(C)** 回答・リンクを決まった画面と同じ
  入口に統一する。いずれにせよ `answersTab`・`linksTab` の testId の扱いが変わるので、決まるまで YAML のタブは消していない。
- **Q4 「回答の表・変える」の「変える」**。絵の日程の1行にあるが、決めた日を変える操作は API に無い（局面は SELECTING_SHOP から戻らない。
  ADR-0035）。「変える」を出すなら新しい操作（API の変更）が要る。案: **(A)** 「変える」は出さない（推奨）。**(B)** 日を決め直せるようにする（別件）。
- **Q5 手順の開閉**。`current` 以外を人が開けるか、同時に何個開くかは絵から読めない。案: **(A)** `done` は1行の入口でだけ開き、`current` は常に開く（推奨）。

## 帰結

- 契約（確定）: `gathering-scheduling-browser-interface.yaml` 0.34.0 の追補33（`stepFlow`・`mapPlacement` を足す。既存のタブ・地図の節は消さず注記だけ）。
  `.feature` は変えない（並びと位置は業務規則ではない。ADR-0075 決定4と同じ扱い）。
- 実装（別チケット）: 会の画面の骨組み（テンプレート・JS・CSS）。日程を聞き中の表（ADR-0080）を先に直すと衝突が少ない。
- 受け入れ: `gathering-candidate-date` を局面で見えるか確かめている step は、手順の畳みで見えなくなるものがある。tester が洗い出す。

## 確認事項への回答（2026-10-11、人間が調整役とのチャットで合意）

| ID | 回答 | 契約での扱い |
|---|---|---|
| Q1 決まった後の PC の地図 | **A** 右の列（designer が決まった PC を描き済み） | `mapPlacement` SF-1・SF-2 が FINALIZED にも掛かる |
| Q2 日程を聞き中の PC の地図 | **A** 出す（検索基点だけ） | `gathering-scheduling-map` |
| Q3 回答・リンクのタブ | **A** タブはなくす。回答の表の入口は日程の手順、リンクは節 | `shopSelectionPanel` 廃止、`gathering-step-answers-open`、目的 `gathering-shop-select-tab-*` 4件を削除 |
| Q4 「変える」リンク | **A** 出さない | `stepFlow.step.foldedRule` に明記 |
| Q5 畳んだ手順の開閉 | **A** 済みは1行の入口でだけ開く | 同上 |

暫定だった決定3は、これで確定する。展開したときの見た目はキャンバス版71に絵があるが、この ADR の起草者は読んでいない。契約が固定するのは挙動だけ。

## 決定の続き（2026-10-11、KEN-64、決める点3の暫定を外す。キャンバス「3 会の画面の並び」案C、3-追加 案A。契約 会 0.36.0 の追補37）

人間は「いったん①で進める。あとで実物を見て確認」と言った。**暫定を外して確定扱いにする**。実物を見て変えたくなったら、新しい ADR で覆す。
上の決定1〜4はそのまま生き、次を足す。

5. **畳んだ手順と入口**（`stepFlow.summary`・`foldedEntrance`）。畳んだ（`done`）手順で見えるのは、1行の要約 `gathering-step-summary`（新設。日程なら決まった日、店なら決まった店の名前）と、
   日程の手順だけにある入口 `gathering-step-answers-open` だけ。入口の見える文言は「**回答の表**」（「変える」は含めない。Must）、畳んだ日程の行の**右**に置く（高さ44px以上。キャンバスの40pxは
   ADR-0066 の不変条件に足りない）。店の手順は決まったあと、開くものが無い（ADR-0062 決定4で、ほかの店の票は出さない）ので入口を持たない。畳んだ中身は DOM に残り、属性は変わらない
   （旧 `finalizedSummary.answersContent` の文を引き継ぐ）。
6. **地図の置き場の確定**（`mapPlacement` SF-5〜SF-9）。PC は手順（と下の節）が左の1列、地図が右。スマホは、店を選び中は「店」の手順の中で 入口（店を探して入れなおす）→ 地図 → 店の一覧 → 確定ボタン、
   決まったあとは「決まり」の手順の中で 決定の文 → 地図。決まったあとも地図は残す。**全幅の地図（ADR-0069 決定4・ADR-0063 決定2）はPCもスマホも廃止**。地図は各局面で幹事自身の検索基点を1つ出す
   （新設 `gathering-scheduling-map-origin-marker`・`gathering-shortlisted-shop-map-origin-marker`）。店を選び中の地図に基点を足すのは、参加者側の「基点を出さない」規則を幹事側には当てない、という読み替え。
   これに合わせて `responseTableWidth` の RT-1（PCは手順の列の幅）と RT-2（手順の枠の中は許す）を読み替える。
7. **リンクの節**（`linkSection`、`gathering-link-section`、入口 `gathering-link-section-open`）。店を選び中と決まったあとは、手順の下の節に「回答リンク N本」・答えた／まだ・（店を選び中だけ）「リンクを発行」・
   一覧の入口を置く。一覧は入口を押すと開く。日程を聞き中は今のまま（日程の手順の中、ADR-0076 の PH-1〜PH-4）。
8. **廃止**。店を選び中の 店／日程／回答／リンク のタブ（契約はすでに追補33で廃止済みで、残っていた注記を整理）、`finalizedSummary` の `answersOpen`・`linksOpen`・`answersContent`・`decisionBanner.map.layout`。
   目的 `gathering-decision-answers-open`・`gathering-decision-links-open` を `allowedPurposes` から外し、`gathering-link-section-open` を足す。
9. **KEN-61 の日程の表**（追補34〜36）は、日程の手順の中身としてそのまま使う。

### 新しい testId と、受け入れの変更表

| 区分 | testId・対象 | 内容 |
|---|---|---|
| 新設 | `gathering-step-summary` | 畳んだ／これからの手順に1つ。表示専用 |
| 新設 | `gathering-link-section` | 店を選び中・決まった局面だけ。手順の下の節 |
| 新設 | `gathering-link-section-open`（目的も同名） | 一覧の開閉。`aria-expanded` |
| 新設 | `gathering-scheduling-map-origin-marker` | 日程を聞き中の地図の検索基点。表示専用 |
| 新設 | `gathering-shortlisted-shop-map-origin-marker` | 店を選び中の地図の検索基点。表示専用 |
| 追補33で新設済み | `gathering-step`・`gathering-step-answers-open`・`gathering-scheduling-map` | 属性・文言の Must を追補37で足した |
| 廃止 | `gathering-decision-answers-open`・`gathering-decision-links-open` | 後継は `gathering-step-answers-open`・`gathering-link-section-open` |
| 廃止（追補33から） | `gathering-shop-select-tab-{shop,schedule,answers,links}` | 受け入れの DSL にまだ残っている |

| 受け入れ・L5 の直す先 | 内容 |
|---|---|
| `tests/acceptance/dsl/gathering_scheduling_browser.py` の `ensure_finalized_answers_are_open`・`ensure_finalized_links_are_open`・`ensure_selecting_shop_{schedule,answers,links}_tab_is_open` | 手順の入口 `gathering-step-answers-open`（回答の表）と `gathering-link-section-open`（リンクの一覧）を開くものに置き換える。日程のタブを開く呼び出しは不要になる（日程の中身は DOM に残る） |
| 同 `assert_finalized_answers_and_links_entrance_is_functional`・`assert_selecting_shop_tab_panel_is_functional`・`assert_schedule_tab_shows_only_the_decided_date_chip`（テスト `test_gth_organizer_decision_answers_and_links_entrance_is_functional`・`test_gth_selecting_shop_tab_panel_is_functional`・`test_gth_schedule_tab_shows_only_the_decided_date_chip`） | 新しい入口（`aria-expanded`、SF-5a・SF-6・SF-7、LS-1〜LS-3）の検査に書き直す。タブの検査は消す |
| `tests/ui_invariants/test_layout_sanity.py`・`test_render_invariants.py`・`test_zz_capture_states.py` | `gathering-shop-select-tab-*`・`gathering-decision-*-open` を押す箇所を新しい入口に。全幅の地図の検査（ADR-0069 決定4）を SF-1・SF-5・SF-8 に置き換える |
| `.feature` | 既存の本文は**変えない**（TDR-GTH-65・66・67 の本文は成り立つ。67 の「地図いっぱい」はコメントの読み替え）。**TDR-GTH-75 を足した**（店を選び中でも回答の表と回答リンクの一覧を見られる。人間が2026-10-11に承認。`gathering-step-answers-open` と `gathering-link-section-open` を開く step の定義は KEN-64 の developer が足す） |

### 聞いておく点（キャンバスと契約の食い違い）

- 日程を聞き中のキャンバスは、リンクの行を日程の手順の中に描いている（PC・スマホとも）。契約は日程を聞き中を今のままにし、リンクの節は店を選び中と決まったあとだけにした（上の7）。
- 決まった画面のキャンバスは「回答の表」の入口を日程の行と決まりの手順の下の2か所に描く。契約は入口を日程の行の1か所にした（SF-6）。もう1つは見た目として置いてよいが、押すと同じものを開く別の testId は置かない。
- スマホのキャンバスは、日程と店の畳んだ行に右向きの矢印を描く。契約は店の行の入口を要求しない（5）。矢印は見た目。
- キャンバスの入口ボタンの高さは40pxで、契約の44pxに足りない。
- 日程を聞き中の PC の表は、キャンバスでは幅540pxの列に入って7日ずつ横に送る。契約の RT-1・RT-2 は全幅・枠なしを求めていたので読み替えた（6）。
