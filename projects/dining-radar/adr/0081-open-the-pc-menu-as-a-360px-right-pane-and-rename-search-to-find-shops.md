---
id: 0081
scope: project/dining-radar
status: 提案中
date: 2026-10-11
approved_by: null
supersedes: []
superseded_by: null
relates_to: [ADR-0059, ADR-0066, ADR-0069, ADR-0075, ADR-0077, ADR-0078]
---

# ADR-0081: PC の≡を右から幅360pxのペインにし、スマホの下部バーの「さがす」を「店を探す」に改名する

> **承認者向けサマリ**: KEN-58 の人間の決定 7 と 8。**決定1**: PC の≡（`candidate-primary-nav-menu-toggle`）を押すと、いまの「≡の下に出る小さな吹き出し」ではなく、
> **画面の右端から幅360pxのペイン**が出る。背景を暗くし、×・背景・Esc で閉じる。中に動いている会が並び、押すとその会が開く。
> **決定2**: スマホの下部バーは3つのまま、「さがす」を「店を探す」に改名する。メニューの同じ項目も「店を探す」。
> これは ADR-0066 決定1・3（吹き出しは≡の下に右端を揃えて開く）を**覆す**。ペインの中の会の並びはホームと同じ規則（ADR-0078）にする。
> **まだ決めていないこと（人間に聞く）**: ペインの各会に「次にやること」を出すか（Q1。決定2「小さな行に次にやることを付けない」との釣り合い）、
> 下部バーとメニューの並び順を絵に合わせて入れ替えるか（Q2。決定文は改名しか言っていない）。

## 文脈

### 検証の申告

実際に `Read` したもの: `candidate-search-browser-interface.yaml`（1.17.0）の `renderModes`・`gatheringEntry` 全体（`menuToggle`・`menuPanel`・
`menuDestination*`・`mobileBar*`・`primaryNavigationGeometry`・`navIcons`・`crossContractReference`）、ADR-0077、
`gathering-scheduling-browser-interface.yaml` の `crossFileSharedNavigation`、キャンバスの p7・p8 の付箋と Nav-PcPane・Nav-PcMenu・Nav-SpN1・Nav-SpN2 の文字。
テンプレート `organizer_primary_nav.html`・`home.html` に「さがす」の文言があることだけ確認（中身は読んでいない）。

### 現状

- 契約は、`menuPanel` の開き方（≡の下、右端を揃え、画面の外に出ない）を ADR-0066 の `primaryNavigationGeometry.twoColumnLayout` で固定し、
  L5 の検査（不変条件(o)）がそれを測っている。パネルの中身は「行き先2つ（さがす・ランチ会）→ アカウント操作」。
- ラベルの文言（「さがす」「ランチ会」）は契約が固定していない。そのため改名は契約の変更として現れない。
- 候補画面は進行中の会の**件数**だけを会の API から読む（`getInProgressGatheringCount`）。会の一覧そのものは読まない。

## 決定

1. **ペイン**（`primaryNavigationGeometry.menuPane`、PC＝`twoColumnLayout` のみ）。`menuPanel` を開くと、(a) 画面の右端に貼り付き（ペインの右端＝画面の右端）、
   (b) 画面の高さいっぱい（上端＝画面の上端、下端＝画面の下端）、(c) 幅は**360px**（許容1px。作図上の値で未実測なので確認事項Q4）、(d) 左端は画面の外に出ない。
   ペインの外は暗くする `candidate-primary-nav-menu-backdrop`（新設、押すと閉じる）。ペインの中に `candidate-primary-nav-menu-close`（新設、×）。**Esc でも閉じる**。
   開く操作（`menuToggle`）と閉じるとフォーカスが `menuToggle` に戻ることは `menuToggle` の既存の規則に従う。
2. **ペインの中身と並び**: 上から (a) `menuDestinationGathering`（ランチ会）と、その下に**動いている会 1件につき1つ**の `candidate-primary-nav-menu-gathering-item`
   （新設。`data-gathering-id`・`data-gathering-phase`・現在表示中の会なら `data-current="true"`・`data-next-action`。押すとその会の画面へ）、
   (b) `menuDestinationSearch`（店を探す）、(c) 区切りのあとにアカウント操作（`auth-password-change-open`・`auth-sign-out`）。
   「ランチ会をつくる」の入口は既存の `gathering-create-open`（`organizerGatheringList` のもの）を再利用せず、ペイン専用の項目にするかを Q3 で聞く。
   会の並びは**ホームと同じ規則**（動いている会だけ、API の並び＝作った日の新しい順。ADR-0078）。件数の上限は決めない（ペインの中でスクロール）。
3. **覆すもの**: ADR-0066 決定1・決定3の `menuPanel`「≡の下に右端を揃えて開く」→ 決定1のペイン。`menuPanel` の「行き先2つが先、アカウントが後」→ 上の並び（行き先の
   順は ランチ会→店を探す に変わる）。L5 の不変条件(o)（開く向き）は、ペインの右端＝画面の右端・左端が画面の中、の検査に置き換える。
4. **データ**: 候補画面（と会の画面群）はペインのために進行中の会の**一覧**を読む（`listGatherings` の読み取り）。`getInProgressGatheringCount` は
   `menuDot` と下部バーの数の丸のために残る（`crossContractReference` に一覧の読み取りを足す）。API は変えない。
5. **スマホの下部バー**: 3つ（`candidate-primary-nav-search`・`-gathering`・`-account`）のまま。「さがす」の見える文言を**「店を探す」**にする。メニュー側
   （`menuDestinationSearch`）も「店を探す」。**この文言は契約の Must にする**（人間が決めた文言の改名で、契約が固定しないと実装が古い文言のまま緑になる。
   ADR-0066 が記録した型と同じ）。`mobileBar` の「常に3つ・欠けない」と `mobileBarAccount` のシートの規則は無変更。
6. **testId・目的の追加**: `candidate-primary-nav-menu-close`・`-menu-backdrop`・`-menu-gathering-item`（目的 `candidate-primary-nav-menu-close`・
   `-menu-backdrop`・`-menu-gathering-item`）。`candidate-search-browser-interface.yaml` の `allowedPurposes` に足す。

## 確認事項（人間に聞く。勝手に決めていない）

- **Q1 ペインの各会の「次にやること」**。キャンバスのペインは各会に「次: 日を決める」を付けているが、決定2（ホームの小さな行は次にやることを付けない）と釣り合わない。
  案: **(A)** 絵どおり付ける（推奨。ペインは「いまここから次の一手へ飛ぶ」ためで、ホームの小さな行とは役割が違う。ただし ADR-0078 Q2 の値の決め方が前提）。
  **(B)** ホームに合わせて付けない（ペインは名前と札だけ。契約が小さい）。
- **Q2 並び順**。キャンバスの下部バーは「ランチ会／店を探す／アカウント」、ペインも「ランチ会→店を探す」。いまは「さがす／ランチ会／アカウント」。決定文は改名しか言っていない。
  案: **(A)** 絵に合わせて入れ替える（推奨。板の裁定。左から ランチ会・店を探す・アカウントと固定。位置の Must）。**(B)** 順序は今のまま（さがすが左）。
- **Q3 ペインの「ランチ会をつくる」**。絵にある。案: **(A)** ペイン専用の項目として足す（新しい押す部品）。**(B)** 足さない（作成はホームで行う）。
- **Q4 幅360px**。作図上の値で未実測。案: **(A)** 360px（許容1px）をそのまま Must にする（人間の言葉どおり。推奨）。**(B)** 幅は固定せず、右端貼り付き・高さいっぱいだけを Must にする。
- **Q5 探す画面自体の名前**。候補画面の見出しは「ランチ候補をさがす」。ナビの改名に合わせて「店を探す」にするかは決定文に無い。案: **(A)** 変えない（推奨）。**(B)** 揃える。
- **Q6 「ランチ会 N」の数の丸**（ADR-0077 で範囲外にした）は今回も扱わない。

## 帰結

- 契約（ドラフト）: `candidate-search-browser-interface.yaml` 1.17.0→1.18.0 の追補（`menuPane`・`navLabels`・`menuClose`・`menuBackdrop`・`menuGatheringItem`）。
  `candidate-search.feature`・`gathering-scheduling.feature` は変えない（ナビの位置・文言は UI の構造。ADR-0075 決定4と同じ扱い）。
- 実装（別チケット）: PC のナビ（`organizer_primary_nav.html`・`home.html`・CSS）、候補画面と会の画面群が一覧を読む処理、L5 の不変条件(o)の置き換え。
- ADR-0066 は部分的に覆される（決定1・3のメニューの開き方）。ADR-0066 本体の `superseded_by` は埋めない（決定2＝位置は Must、決定4以降は生きている）。
