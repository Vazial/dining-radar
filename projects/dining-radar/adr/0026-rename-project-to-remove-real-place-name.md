---
id: 0026
scope: project/dining-radar
status: 承認済み
date: 2026-08-20
approved_by: "本PRのマージをもって承認（人間裁定 2026-08-20: 『プロジェクト名の toyama は消したい』。
  同日の選択肢提示に対して、名前は `dining-radar`／`dining_radar`（現状維持）／`Dining Radar`、
  IDプレフィックスは `TDR` 据え置き、漢字の「富山」はTDR側のみ除去、ブランチとrulesetは据え置き、
  を人間が選んだ）"
supersedes: []
superseded_by: null
relates_to: [P-01, P-04, P-06, P-10, ADR-0002, ADR-0004, ADR-0019, ADR-0021]
---

# ADR-0026: プロジェクト名から実在の地名を外し `dining-radar` へ改名する

> **承認者向けサマリ**: 公開リポジトリ上のプロジェクト名 `toyama-dining-radar` が、この製品自身の
> 方針（`product-brief.md` §4・ADR-0002「実在の地名・生活圏が推測できる情報を Git に置かない」）と
> 逆を向いていたため、`dining-radar` へ改名する。**実装コードは1文字も変わらない**——Pythonパッケージは
> 以前から `dining_radar` であり地名を含んでいなかった。シナリオIDプレフィックス `TDR` は据え置く。
> **この改名だけでは公開リポジトリから地域の露出は消えない**（帰結節に残存箇所を列挙する）。

## 文脈

このリポジトリは公開されている（`gh repo view` の `visibility` が `PUBLIC`）。

`product-brief.md` §4 は「実在の検索地点、地名、座標、既定探索距離、生活圏が推測できる例を Git に
置かない」と定め、ADR-0002 は同じ境界を外部データについて敷いた。実装はこの方針を守っており、検索
基点はサーバの非公開設定（`HOTPEPPER_SEARCH_LATITUDE` 等、`render.yaml` で `sync: false`）に閉じ、
ブラウザへも Git へも出していない。**にもかかわらずプロジェクト名そのものが実在の県名を名乗っていた。**
方針と名前が逆を向いている状態である。

2026-08-20 のデザイン検討で人間が「プロジェクト名の toyama は消したい」と述べ、そのセッションの
スコープ外として本作業に切り出した。

実測（`main` = PR #107 マージ時点、tracked のみ）は次のとおりで、切り出し時のメモの見積もり
（170ファイル/629箇所）とは大きく違った。差は本体の作業コピーに存在するビルド生成物
（`node_modules`・`__pycache__` 等）を数えていたことによる（FR-019）。

- `toyama-dining-radar`（ケバブ）130箇所 ＋ `Toyama Dining Radar`（表示名）13箇所 ＝ **57ファイル/143箇所**
- **`toyama_dining_radar`（スネーク）は0箇所**。Pythonパッケージは以前から `dining_radar` であり、
  地名が入っていたのは `pyproject.toml` の `name = "toyama-dining-radar"` の1行だけだった
- リポジトリ内に `*.egg-info` は追跡・未追跡とも存在しない
- ブランチ保護の必須チェックは `protect main`・`protect project/toyama-dining-radar` とも
  `L0: 統治文書の整合(govlint)` の**1本のみ**（`gh api repos/:owner/:repo/rulesets` で実測）。
  `ci-<project>.yml` のジョブ名は required に入っていないため、ワークフローの改名は
  GitHub 側の設定変更を伴わない

### 本改名を一度やり直している

本改名は2026-08-20に一度 `f3f1cac`（PR #103 直後の `main`）の上で作り、**未pushのローカルブランチ
`docs/tdr-cs-origin-and-walking-time` と衝突することが分かって保留した**。あちらは `adr/0025`
（検索基点と徒歩時間を認証済み画面へ出す判断）と探索ラフ3枚を旧パス配下に足す1615行の変更で、
ディレクトリを丸ごと動かす本改名とは構造的にぶつかる。**衝突する2つのうち、作り直しが安いほうを
後にする**——本改名の中身は機械的な置換であり再現の費用がほぼ無い——という理由で、あちらを先に
通した（PR #106・#107）。本ADRとこの改名は、そのマージ後の `main` の上で作り直したものである。

## 決定

### 1. 表記を4つに分けて割り当てる

| 用途 | 旧 | 新 |
|---|---|---|
| ディレクトリ | `projects/toyama-dining-radar` | `projects/dining-radar` |
| Pythonパッケージ | `dining_radar` | `dining_radar`（**変更しない**） |
| 配布名（`pyproject.toml` の `name`） | `toyama-dining-radar` | `dining-radar` |
| 表示名 | Toyama Dining Radar | Dining Radar |
| ADRの `scope` | `project/toyama-dining-radar` | `project/dining-radar` |
| CIワークフロー | `.github/workflows/ci-toyama-dining-radar.yml` | `.github/workflows/ci-dining-radar.yml` |

Pythonパッケージを据え置くことが、この案を選んだ理由の中心である。`src/dining_radar/**` のパス、
全 `import`、`DJANGO_SETTINGS_MODULE`、`static/dining_radar/**`、coverage の `source`、
pytest-gremlins の `paths` は**一切動かない**（`dining_radar` は159箇所あり、そのすべてが無変更）。
改名によって import 解決が壊れる経路が構造的に存在しなくなる。

### 2. シナリオIDプレフィックス `TDR` は据え置く

`TDR` は Toyama Dining Radar の頭字だが、実測738箇所に及び、その中には**承認済み契約の
シナリオID**（`TDR-AUTH-01`〜・`TDR-CS-01`〜）、CSSクラス `.tdr-*`、テスト関数名 `test_tdr_cs_14_*`、
`reviews/audit-tdr-cs*.md` のファイル名が含まれる。契約の変更は人間の承認点であり、地名を外すという
目的に対して承認点を1つ増やすだけの費用がある。

据え置く代わりに、`meta/scenario-id-prefixes.md` の `TDR` 行から地名（「富山県庁周辺の」）を落とす。
これにより **`TDR` はどこにも復号先を持たない不透明なトークンになる**。プレフィックスが地名を露出
させていたのは頭字それ自体ではなく、台帳の説明文だった。

### 3. 承認済みADR本文の識別子置換を、本改名に限って行う

`meta/templates/adr.md` の運用ルール（P-06）は「承認後の本文編集は禁止」と定める。本改名は25本の
承認済みADRの `scope:` と本文中のプロジェクト名を書き換えるため、この規則に触れる。**識別子の機械的な
置換であり、決定内容・文脈・代替案・帰結のいずれも変えない**ことを明示して行う。置換しない場合、
`scope:` が実在しないプロジェクトを指し、本文の相互参照が全て切れる——規則が守ろうとしている
「決定の記録が後から書き換えられないこと」は、この置換によって損なわれない。

あわせて `adr/0019` の実データ引用「あり：富山大和駐車場」を「あり：〈実在の商業施設名〉駐車場」へ
伏せ字にする。**これは判断の変更ではなく、ADR-0002・ADR-0004 の境界に対する既存の違反の是正である**
——ADR-0019 自身が同じ段落で「駐車場名が実質的に周辺の地名・施設名を開示しうる」と警告しながら、
その実例を生の値のまま本文に残していた。

### 4. gitブランチと GitHub ruleset は改名しない

`project/toyama-dining-radar` ブランチと ruleset `protect project/toyama-dining-radar` は据え置く。
このブランチは `main` より大きく遅れており refresh or retire の判断待ちである（`activeContext.md`）。
改名するとブランチ削除という破壊的操作を伴うため、その判断とセットで扱う。

### 5. git履歴は書き換えない

過去コミットに旧名が残ることは受け入れる。公開リポジトリの履歴書き換えは別種の判断であり、必要なら
人間が別途決める。

## 検討した代替案

- 案A: `lunch-radar`（パッケージ `lunch_radar`）/ 不採用の理由: 「ランチ」が名前に出る利点はあるが、
  src配下のパッケージ名・全import・settings module・static配下など**159箇所が追加で動く**。地名を
  外すという目的に対して、import解決が壊れうる面を新たに開く費用が見合わない
- 案B: `lunch-candidate-radar` / 不採用の理由: 「候補を比べる」が最も明示的だが、差分規模は案Aと同等で、
  名前が長い
- 案C: `TDR` も新名称に合わせて変更する / 不採用の理由: 決定2のとおり、承認済み契約のシナリオIDが動き、
  改名PRに人間の再承認事項が1つ増える。頭字それ自体は復号先が無ければ地名を露出させない
- 案D: 何もしない / 不採用の理由: 製品自身の方針（product-brief §4・ADR-0002）と名前が矛盾したままになる

## 帰結

**この改名だけでは、公開リポジトリから地域の露出は消えない。** 現在の木に残るのは次の4つである。

1. **過去コミット**（決定5のとおり意図的に残す）
2. **ブランチ名 `project/toyama-dining-radar` と ruleset 名 `protect project/toyama-dining-radar`**
   （決定4のとおり意図的に残す）
3. **`toyama-weekend-radar`**（Codex担当・休止中の別プロジェクト。main上にディレクトリは無いが、
   名前は `activeContext.md`・`meta/adr/0033`・`meta/guardrails.md` に、
   `meta/scenario-id-prefixes.md` の `TWR` 行には「**富山市近郊**の週末イベント提案」と平文で残る）。
   別プロジェクトの改名になるため本ADRのスコープ外であり、**人間が別途判断する**
4. **`projects/connpass-session-radar/contracts/daily-digest-contract.yaml`** の例示
   「富山県内の勉強会」。別プロジェクトの契約であり、契約の変更は人間の承認点であるため本ADRでは触らない

つまり `TDR` を据え置いた判断（決定2）が地名を残しているのではなく、**残っているのは上の4つ**である。

その他の帰結:

- **CIの必須チェックは変わらない**。`ci-dining-radar.yml` のジョブ名は required に入っていないため、
  GitHub側の設定作業は発生しない（文脈節の実測による）
- **Render の service 名が `dining-radar` になる**。ADR-0021 の無料公開構成はまだ resource を作成して
  いないため既存デプロイへの影響は無いが、公開originは `dining-radar` 由来の名前になる
- `.claude/launch.json` の preview 設定名が `dining-radar-live` / `dining-radar-app` /
  `dining-radar-design-preview` に変わる
- **ローカルの開発環境は入れ直しが要る**。`pip install -e .` が作る editable install は配布名と
  旧パスを覚えているため、改名後は `pip install -e ".[dev]"` をやり直さないと解決先が古いままになる
- 25本の承認済みADRと契約・reviews・friction-log の本文にプロジェクト名の置換が入るため、本PRの差分は
  行数の割に読む価値が低い。**レビューは「置換以外の差分があるか」に絞ってよい**（置換以外は
  本ADR・`adr/0019` の伏せ字・`meta/scenario-id-prefixes.md` の `TDR` 行・ブランチ名を旧名のまま
  据え置いた3箇所・activeContext・friction-log の FR-019/FR-020 だけである）
