---
id: 0051
scope: project/dining-radar
status: 承認済み
date: 2026-09-09
approved_by: "人間裁定（2026-09-09 チャット選択肢UI）: 前段のarchitectがFR-028の流儀（食い違い・
  未決を勝手に解消せず報告する）に従い『organizerGatheringCreate.candidateDateRow（会をつくる画面）を、
  addCandidateDateForm（幹事ダッシュボードの候補日追加）と同じカレンダーへ統一するかどうかが未決』と
  契約ファイル内に申し送ったのに対し、『両方カレンダーにする。会をつくるときも、あとから足すときも
  同じカレンダーの複数選択。理由は手触りが揃い、最初から複数日を選べること』と裁定した。"
supersedes: []
superseded_by: null
relates_to: [P-02, P-06, ADR-0013, ADR-0035, ADR-0038, ADR-0049, TDR-GTH-01,
  TDR-GTH-23, TDR-GTH-46, TDR-GTH-47]
---

# ADR-0051: 会をつくる画面の候補日入力も、候補日を足す画面と同じカレンダーの複数選択にする

> **承認者向けサマリ**: この製品には候補日を入力する画面が2つある——会を新規につくる画面
> （E-2、契約上は`organizerGatheringCreate`）と、会をつくった後で候補日を足す画面（A①、
> `addCandidateDateForm`）である。直前のADR-0049決定3は、A①だけをカレンダーの複数選択に
> 作り替え、E-2は行の追加・削除（1行ごとに日付＋時刻を入力し、「候補日を足す」ボタンで行を
> 増やし、「削除」ボタンで行を減らす）のまま残した——2つの入力面を統一するかどうかを、
> 契約ファイル内の申し送り（`gathering-scheduling-browser-interface.yaml`の
> `organizerGatheringCreate.candidateDateRow.note`）として人間の確認待ちにしていた。人間が
> 2026-09-09のチャットで「両方カレンダーにする」と裁定した。本ADRはE-2の行ベース入力
> （`candidateDateRow`・`addRow`・`removeRow`）を廃し、A①と同じ形のカレンダー複数選択
> （この画面専用のtest id、`gathering-create-candidate-date-calendar`・
> `gathering-create-candidate-date-day`）へ置き換える。会をつくるのに候補日1つ以上が
> 必要という既存の決定（ADR-0035決定1・D10）、選べるのは明日以降のみ・時間は12:00–13:00
> 既定というADR-0049決定3の性質は変えない——変わるのは入力面の形だけである。

## 文脈

### 0. 検証の申告（meta/adr/0039）

本ADRが前提とする既存契約の記述は、`gathering-scheduling-browser-interface.yaml`
（contractVersion 0.10.0、本ADRと同一作業で0.11.0へ改訂）を実際に読んで確認した。特に
`organizerGatheringCreate`節（行ベースの候補日入力、`candidateDateRow`/`addRow`/`removeRow`）
と`organizerDashboard.candidateDateList.addCandidateDateForm`節（カレンダーの複数選択、
ADR-0049決定3が新設した`calendar`/`dayCell`）を比較し、両者の差分が「日付・時刻の入力手段」
だけであることを確認した。業務規則（候補日1つ以上・明日以降のみ・重複拒否）は両画面とも
API層（`gathering-scheduling-api.yaml`の`createGathering`・`addCandidateDates`、いずれも
本ADRでは変更しない）が共通で強制していることも確認した。`gathering-scheduling.feature`の
TDR-GTH-01・22・23・46・47も読み、いずれも業務の言葉（「候補日を用意している」「候補日を
足す」「幹事が会をつくろうとしている」等）で書かれており、入力手段（行かカレンダーか）を
指定していないことを確認した——したがって本ADRはこれらのシナリオ本文を変更しない。designer
の画面材料は本ADRでは新たに参照していない——本ADRは既に承認済みの2つの入力面（行とカレンダー）
のうち片方を他方に揃えるという契約内の整合の問題であり、新しい画面デザインの起こし直しを
必要としないとarchitectが判断したため。確認していないのは、この契約変更を実装したコードの
挙動そのもの——architectは実装コードを読まない（`.claude/agents/architect.md`の禁止事項）。

### 1. 何が未決だったか

ADR-0049決定3（2026-09-08人間裁定「候補日はカレンダーで複数選択する」）は、
`addCandidateDateForm`（幹事ダッシュボードから既存の会に候補日を追加する画面、A①）の
単一の日時入力を、複数選択カレンダーへ置き換えた。同決定の本文自身が、
`gathering-scheduling-api.yaml`のヘッダコメントの記述「カレンダーはE-2でもA①でも同じ
入力面を使う」に触れていたが、その回の依頼の名指しがA①のみだったため、
`organizerGatheringCreate`（会を新規につくる画面、E-2）の行ベース入力
（`candidateDateRow`、1行ごとに日付＋時刻・`addRow`で行を増やす・`removeRow`で行を減らす）
はそのまま残し、2つの入力面を統一するかどうかを契約ファイル内の申し送り
（`organizerGatheringCreate.candidateDateRow.note`）として人間の確認待ちにした
（FR-028の流儀——食い違いや未決を勝手に解消せず報告する）。

### 2. 人間の裁定

2026-09-09のチャット（選択肢UI）で、人間は「両方カレンダーにする。会をつくるときも、あとから
足すときも同じカレンダーの複数選択」と裁定した。理由は「手触りが揃い、最初から複数日を選べる」
ことである。

## 決定

### 決定1. `organizerGatheringCreate`の候補日入力を、`addCandidateDateForm`と同じ形のカレンダー複数選択に置き換える

`gathering-scheduling-browser-interface.yaml`の`organizerGatheringCreate.candidateDateRow`
（`gathering-create-candidate-date-row`、1行ごとの`dateInput`
〔`gathering-create-candidate-date-input`〕、`addRow`
〔`gathering-create-add-candidate-date-row`〕・`removeRow`
〔`gathering-create-remove-candidate-date-row`〕）を全廃する。代わりに
`organizerGatheringCreate.calendar`（新設、`gathering-create-candidate-date-calendar`の
`gathering-create-candidate-date-day`セル、新設purpose
`gathering-create-candidate-date-day-select`）を設け、`addCandidateDateForm.calendar`
（`gathering-add-candidate-date-day`）とまったく同じ日セルの形・同じ「明日以降のみ」の
非活性規則・同じ「12:00始まり」のUI補助を、この画面専用のtest idで再現する。

**test idは共有しない**（設計判断）: E-2とA①は別のDOM位置（前者は独立した作成画面、後者は
幹事ダッシュボード内のインラインフォーム）に別々にレンダリングされる別要素であり、統一する
べきは「同じ入力の形」であって「同じDOM要素」ではない。具体的なUI要素そのものを2画面で
共有すると、一方の画面固有の状態変化（`organizerGatheringCreate`では送信＝会の新規作成で
画面から離れる、`addCandidateDateForm`では送信後もフォームが開いたまま次の入力を待つ）が
同じtest idに異なる`requiredOutcome`を要求することになり、この契約の「1つのtest idは1つの
観測面」という既存の設計原則（ADR-0013起源）を崩す。

### 決定2. 候補日1つ以上の要件・明日以降のみの拒否は変えず、入力面の書き換えに合わせて観測の記述だけを更新する

ADR-0035決定1・D10が確立した「会の作成には候補日1つ以上が必要」という業務規則は変わらない。
`gathering-create-submit`のdisabledStateを、「行の入力チェック」から「選択済みの
`gathering-create-candidate-date-day`が1件以上」へ書き換える——境界条件自体（1つ以上）は
変わらず、観測する対象がカレンダーの選択状態に変わるだけである。

ADR-0049決定3の「明日以降のみ」（`CANDIDATE_DATE_NOT_IN_FUTURE`）は、同決定の本文が
「`createGathering`・`addCandidateDates`の両方に適用する」と既に明記しており、API層の
挙動は変わらない。本ADRは、この画面（E-2）のカレンダーにも同じ非活性規則（今日以前の日を
選べなくする）を明記し、`TDR-GTH-47`（今日または過去の日付は候補日にできない。Given節は
「幹事が会をつくろうとしている」——会をつくる場面を指している）が、この画面を通じて実際に
観測可能になるようにする。

### 決定3. 値入力コントロール・許可されたpurposeの一覧を、行ベースからカレンダーへ揃える

`unavailableControls.valueEntryControlTestIds`から`gathering-create-candidate-date-input`
（廃止する行の日時入力）を外す——`gathering-add-candidate-date-input`がADR-0049決定3で
辿ったのと同じ理由で、カレンダーの日セルは値をただ保持するだけの入力欄ではなく、活性化
それ自体が保留選択のトグルという振る舞いを引き起こす操作的コントロールである。
`allowedPurposes`から`gathering-create-add-candidate-date-row`・
`gathering-create-remove-candidate-date-row`を削除し、
`gathering-create-candidate-date-day-select`を追加する。`browserActions.createGathering`の
`inputs`を、行関連のtest id（`gathering-create-candidate-date-row`・
`gathering-create-candidate-date-input`）から`gathering-create-candidate-date-day`へ
差し替える。

## 検討した代替案

- **統一しない（前段の申し送りの状態を維持する）**: 却下。人間が明示的に「両方カレンダーに
  する」と裁定した。
- **A①をE-2の行ベースへ揃える（逆方向の統一）**: 却下。ADR-0049決定3で人間はカレンダーを
  「きれいなUIのライブラリを使う」理由で明示的に選んでおり、行ベースへ戻す理由が無い。
- **2つの画面で同じtest idのカレンダー・日セルを共有する**: 却下（決定1）。別のDOM要素を
  同じtest idで指すと、画面ごとに異なる送信後の挙動（会の新規作成 対 フォームを開いたまま
  次の入力を待つ）を1つのtest idの下に押し込むことになり、この契約の「1 test id＝1観測面」
  の原則と衝突する。

## 帰結

- `contracts/gathering-scheduling-browser-interface.yaml`（改訂、contractVersion 0.10.0 ->
  0.11.0、本ADRと同一作業で完了済み）:
  - `organizerGatheringCreate.requiredTestIds`・`candidateDateRow`節を全廃し、`calendar`
    （`gathering-create-candidate-date-calendar`/`-day`/`-day-select`）へ置き換えた。
  - `submit.disabledState`・`submit.requiredOutcome`をカレンダーの選択状態を消費する記述へ
    書き換えた。
  - `unavailableControls.valueEntryControlTestIds`・`allowedPurposes`・
    `operationalControlScope`の例示・`browserActions.createGathering.inputs`を整合させた。
  - ヘッダコメントへ2026-09-09追補9を追加し、前段（追補8）が申し送った未決事項の決着として
    記録した。
- `contracts/gathering-scheduling.feature`: **変更していない**——TDR-GTH-01・22・23・46・47は
  いずれも業務の言葉（入力手段を指定しない）で書かれており、本ADRは入力手段だけを変える
  ため、本文を書き換える理由がない。
- `contracts/gathering-scheduling-api.yaml`: 変更しない——`createGathering`・
  `addCandidateDates`のリクエスト形状・拒否コードはADR-0049決定3から変わらない。
- `ARCHITECTURE.md`・`design.md`: 変更しない——本ADRは新しいモジュール境界を生まない
  （既存の`gathering-scheduling`スライス内の、画面間の入力手段の統一に留まる）。

## 未決事項（次工程・人間への申し送り）

1. カレンダーの実装（ライブラリの選定、月送り・週の始まりの曜日等）はADR-0049決定3と同じく
   契約の範囲外——developerの裁量である。
2. E-2とA①のカレンダーがまったく同じ視覚デザインになるか（同じライブラリ・同じ配色）は、
   本ADRが決めることではない——契約が固定するのは日セルの観測面（`data-date`/
   `data-selected`）と業務規則（明日以降のみ・1件以上）だけであり、2画面の見た目の一致は
   designer/developerの裁量に委ねる。
3. 寸法・実機確認は未実測（`meta/adr/0059`決定5どおり）——実測はorchestratorの領分。
4. `gathering_create.js`・`gathering_scheduling_browser.py`（DSL）等、既存の行ベース実装は
   本ADRの対象外——architectは実装コードを読まない・書かない。developerが本ADRに沿って
   実装を作り替える必要があるが、その着手判断はorchestrator/人間に委ねる。

---
<!--
frontmatter（機械可読なメタデータ。meta/adr/0012。meta/tools/govlint.py が検証する）:
- id: ファイル名の採番と一致させる
- scope: meta（A層の決定）か project/<名前>（そのプロジェクトの決定）。採番はscopeごとに独立
- status: 提案中 / 承認済み / superseded
- supersedes / superseded_by: 相手のADRのid。**対称**に書く
- relates_to: 関連する信条(P-XX)・シナリオID・FR-XXX 等。参照先が実在することをlintが検証する
-->
