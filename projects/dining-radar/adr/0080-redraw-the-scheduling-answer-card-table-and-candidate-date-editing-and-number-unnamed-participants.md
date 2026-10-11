---
id: 0080
scope: project/dining-radar
status: 提案中
date: 2026-10-11
approved_by: null
supersedes: []
superseded_by: null
relates_to: [ADR-0056, ADR-0060, ADR-0071, ADR-0072, ADR-0076, ADR-0079]
---

# ADR-0080: 日程を聞き中の答えの札・表・候補日の編集を引き直し、名前のない参加者を「参加者N」と呼ぶ

> **承認者向けサマリ**: KEN-58 の人間の決定 5 と 6。日程を聞いている幹事画面の中身を、**札は案A、表は案B**の混成にし、
> 名前を付けていない参加者を発行順の番号で呼ぶ。**決定1**: 札は「4/6人」・進み具合の棒・「答えた／まだ」。有力な日は列の
> 薄い緑と「有力」の札で、上の説明文は消す。**決定2**: 表は答えていない人も行に入れて「まだ」を付け、合計の数字の下に短い棒を出す。
> **決定3**: 候補日の追加と削除は「候補日を編集」に一本化する（編集中だけ列見出しに ×、右端に「＋足す」）。候補日の札の格子
> （`gathering-candidate-date-list`）と見出し帯・単独の「候補日を足す」は消す。**決定4**: 名前なしは「参加者1・参加者2…」（発行順）。
> **ADR-0060 決定7（有力の説明文）・ADR-0072（並び）・ADR-0076 決定1（候補日の帯と足すボタンの位置）を部分的に読み替える。**
> 契約の要素の削除を伴うので、どの要素の引っ越し先にするかを確認事項Q1・Q2で聞く（YAML は引っ越し先の案を書き、旧要素には注記だけ付けた）。

## 文脈

### 検証の申告

実際に `Read` したもの: `gathering-scheduling-browser-interface.yaml`（0.32.0）の `organizerDashboard` の `candidateDateList`・
`removeCandidateDate`・`addCandidateDateOpen`・`addCandidateDateForm`・`tentativeSelectionAndPreview`・`schedulingLayout`・
`confirmDate`・`participantLinkList`・`responseTable`（全体）、`gathering-scheduling-api.yaml` の `Gathering`・`ParticipantLinkSummary`、
`gathering-scheduling.feature` の TDR-GTH 全シナリオの題、キャンバスの p5・p6 の付箋と GC-PcScheduling・GC-SpScheduling の文字。
実装は `gathering.js` の表の行を作る部分（`gathering-response-table-row`、名前の出し方）だけ見た。**キャンバスは手元の保存済みの写し（版67かは未確認）。**

### 見つけたこと（キャンバスの記述との差）

- キャンバスの付箋は「答えていない人の行が増えるので、表の行の定義が変わる」とするが、**契約はすでに「`ParticipantLinkSummary` 1件につき1行
  （取り消した行も残す）」**で、実装も1リンク1行を作っている（`gathering.js`）。行の定義は変わらず、足すのは「まだ」の見た目と属性。
- キャンバスの絵は答えていない人の日付の欄に「−」を置くが、ADR-0071 は「無い欄は何も描かない（空白）」と決めている（板の裁定）。
  新しい絵が後なので、確認事項Q3で聞く。
- 契約では、有力の説明文（`gathering-response-table-leader-summary`）と候補日の札（`gathering-candidate-date`）が、有力判定の属性
  （`data-current-leader`）と TDR-GTH-59〜62、確定ボタンの対象（`confirmDate.target`）、仮選択の操作（`tentativeSelectionAndPreview`）、
  表の列の塗り（`paintedColumn`）のすべての出どころになっている。**札の格子を消すと、これらの出どころを移す必要がある。**

## 決定

1. **答えの札（案A）**: 日程の手順の頭に「回答 4/6人」＋進み具合の棒＋「答えた 4」「まだ 2」。既存の `gathering-responded-summary`
   （「答えた N」）・`gathering-unanswered-summary`（「まだ M」）をそのまま使い、棒は表示専用の `gathering-responded-progress`（新設、
   `data-responded-count`・`data-active-issued-links`）。上の説明文（「有力 ◯/◯（◯）」の文）は消す。
2. **有力の見せ方**: 有力な日の列を薄い緑で塗り（`paintedColumn` は無変更）、その列の見出しに「有力」の札を付ける。
   `gathering-response-table-leader-summary` の testId を**この札に付け替える**（旧: 表の上の文）。1つの有力な日に1個、同票なら複数、
   0票なら0個、SCHEDULING のときだけ、という規則はそのまま。**TDR-GTH-59〜62 は文面も step 定義の意味も変わらない。**
3. **表（案B）**: 行は今まで通り1リンク1行。各行に `data-has-responded`（"true"／"false"）と `data-participant-ordinal` を足す。答えていない行は
   名前の欄に「まだ」の札を出す（取り消した行は「取り消し済み」）。合計の行（`goingCountRow`）は、数字の下に短い棒を出す（棒は見た目で、
   契約は固定しない）。
4. **候補日の編集（一本化）**: `gathering-candidate-date-edit-toggle`（新設、目的 `gathering-candidate-date-edit-toggle`）。SCHEDULING のときだけ出現。
   押すと編集中（`data-editing="true"`）になり、**編集中だけ** (a) 決まっていない候補日の列見出しに削除（既存 `gathering-candidate-date-remove`）、
   (b) 表の右端に追加（既存 `gathering-add-candidate-date-open`。開くと既存の `gathering-add-candidate-date-form`）が出る。編集中でないとき両方とも出現しない。
5. **候補日の要素の引っ越し**: `gathering-candidate-date`（属性・仮選択・有力の出どころ）は、**表の列見出し `gathering-response-table-header-cell` の中の子要素**
   として置く（1候補日に1個。列見出し1個に `gathering-candidate-date` 1個）。`gathering-candidate-date-list`・見出し帯
   `gathering-candidate-date-heading`（ADR-0076 決定1 の CH-1〜CH-5）は廃止。`addCandidateDateOpen` の位置（CH-2）は決定4の位置に置き換わる。
   並び順（開催日の早い順）は列見出しの並びが持つ。仮選択は編集中でないときの列見出しの押下。
6. **名前のない参加者**: 名前が `null` の参加者の見える名前は「参加者」＋N。N は**取り消したものを含む全リンクを発行順（`issuedAt` 昇順、同時刻は id 昇順）に
   数えた順位**（1始まり。キャンバスの絵のとおり。人間の決定文の読み方と食い違うので Q7 で聞く）。`data-participant-ordinal` は名前の有無によらず全行・全リンク項目に付ける。幹事の画面すべて（表の行・リンクの一覧・
   回答の表・決まった画面の回答）で同じ呼び名にする。参加者自身の画面は対象外（Q6）。API は変えない（順位は一覧の配列の並びから分かる）。
7. **ADR の読み替え**: ADR-0060 決定7（有力の説明文を出す）→ 決定2（札に付け替える）。ADR-0072 決定1の並び(1)(2)(6)→ 札・表・確定ボタンの
   3つにし、候補日の節(6)は廃止。ADR-0076 決定1（候補日の帯と足すボタンの位置）→ 決定4・5。ADR-0076 決定2・3（表の幅・リンクの行）は無変更。

## 確認事項（人間に聞く。勝手に決めていない）

- **Q1 候補日の要素の引っ越し先**。案: **(A)** 列見出しの中の子要素にする（推奨。`gathering-candidate-date` の testId・属性・目的が変わらず、
  TDR-GTH-02・08・10・43・50・51・59〜62 の step 定義の探し方がほぼそのまま）。**(B)** 列見出しそのものに属性を移して `gathering-candidate-date` を廃止
  （要素が1つ減るが、確定・仮選択・削除・有力の step 定義を全部直す）。**(C)** 画面に出さない一覧を DOM に残す（見えない要素を契約に残すので非推奨）。
- **Q2 有力の説明文**。案: **(A)** testId を列見出しの「有力」の札に付け替える（推奨。上の文は消える）。**(B)** testId ごと廃止（TDR-GTH-59〜62 の
  step 定義を属性だけで書き直す）。
- **Q3 答えていない欄の記号**。案: **(A)** 「−」を置く（キャンバスの絵のとおり。推奨）。ADR-0071 の「空白」を読み替える。**(B)** 空白のまま（ADR-0071 のまま。
  「まだ」の札だけが目印になる）。
- **Q4 取り消した行を表に残すか**。案: **(A)** 契約のまま残し「取り消し済み」の札を付ける（推奨）。**(B)** 表から外す（契約の変更。順位が飛んで見える）。
- **Q5 編集中の列見出しの押下**。編集中は仮選択を無効にし、×だけを押せるようにする案（推奨）。編集中でも仮選択を許す案もあるが、列見出しに2つの押し先が並ぶ。
- **Q6 参加者自身の画面**（他の人の名前の並び `gathering-schedule-respondent-item`）の「名無し」も「参加者N」にするか。案: **(A)** 変えない（推奨。順位を参加者に出すには
  API の変更が要り、他人の番号は本人には意味が薄い）。**(B)** 揃える（API に順位を足す）。
- **Q7 番号の数え方**（決定文の「参加者1・参加者2…」とキャンバスの絵がずれている）。絵は「あおい／はると／**参加者3**／ゆい／みなと／**参加者6**」で、名前のある人も数えた発行順の順位。
  決定文のとおり読むと「名前のない人だけを1, 2, 3…と数える」。案: **(A)** 全リンクの発行順の順位（絵のとおり。推奨。番号が一生変わらず、「参加者3がまだ」と言い続けられる。名前のない人が1人目から始まるとは限らない。取り消した行は表に残るので番号は飛んで見えない）。
  **(B)** 名前のない人だけを数える（1, 2, 3…と続くが、誰かが名乗ると後ろの人の番号が繰り上がり、同じ人の呼び名が変わる）。**(C)** (A) で取り消した分を数えない（取り消すと後ろが繰り上がる）。

## 帰結

- 契約（ドラフト）: `gathering-scheduling-browser-interface.yaml` 0.33.0 の追補34・35。`gathering-scheduling.feature` に TDR-GTH-70〜72 を下書きで足す
  （まだの人が表に並ぶ／候補日は編集に切り替えたときだけ外せる・足せる／名前なしは発行順の番号）。API は変えない。
- 実装（別チケット）: 日程の手順（札・表・編集）と名前の出し方（`gathering.js`）。KEN-13（ADR-0072 の実装）の Draft PR #27 と同じファイルを触るので、
  順番は調整役が決める。
- 受け入れ: `gathering-candidate-date-list` を待っている step、`gathering-add-candidate-date-open` を常に押している step（編集に切り替えてから押す）を tester が直す。
