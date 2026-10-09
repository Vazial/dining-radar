---
id: 0074
scope: project/dining-radar
status: 承認済み
date: 2026-10-08
approved_by: "人間裁定 2026-10-08 KEN-24 コメント（チャットで選択肢から選択）"
supersedes: []
superseded_by: null
relates_to: [P-02, P-06, P-08, ADR-0013]
---

# ADR-0074: 見出し横の ⓘ（個別アカウント案内）を廃止し、認証契約の要求を外す

> **承認者向けサマリ**: 監査 A4（KEN-24）。見出しの ⓘ は、マウスを載せると個別アカウントの注意書きが出る印。
> スマホには載せる操作が無く何も起きない。**決定**: ⓘ を消す。
> `authentication-browser-interface.yaml` が要求していた `auth-individual-account-guidance`（と `data-*` 2属性）を
> 契約から外す（0.3→0.4）。ADR-0013 は書き換えず、決定8の末尾に更新の注記を足す。人間が選択肢から選んで確定済み。

## 文脈

- 検証の申告: `Read` したのは HANDOFF.md、architect 役定義、ADR-0013 全体（決定8）、
  `authentication-browser-interface.yaml` 0.3、`home.html` の `candidate-account-note`、監査 A4。実行はしていない。
- ADR-0013 決定8は「指摘1（ⓘ）は契約変更不要・ツールチップ化」と判定した。今回は消すので、契約の要求の側を外す必要がある。
- 契約が要求していた箇所: `browserControlSurface.authenticated.requiredTestIds.individualAccountGuidance`、
  `semanticObservations.individualAccountGuidance`（testId と `data-auth-account-use`・`data-auth-credential-sharing`）、
  `browserActions.signIn.success.present` の testId、同 `requiredSemanticObservations`。

## 決定

1. ⓘ（`auth-individual-account-guidance`、`home.html` の `candidate-account-note`）を消す。
2. `authentication-browser-interface.yaml` から上の4箇所を外す。`renderModel` の「存在は DOM に在ること」の規則は
   無変更（文中の `individualAccountGuidance` への参照だけ外す）。禁止 testId には足さない（新しいルールを足さない）。
3. 契約は 0.3→0.4。`authentication.feature`・`authentication-api.md` は無変更（個別アカウントでサインインできる
   振る舞いは TDR-AUTH-02 が持つ）。
4. ADR-0013 は本文を書き換えず、決定8の末尾に「2026-10-08 更新: ⓘ は廃止（ADR-0074）」と注記する。本ADRは
   ADR-0013 を `supersedes` せず `relates_to` で参照する（ADR-0013 の主題は方針の確立で、決定8のうち ⓘ だけが変わる）。

## 検討した代替案

- 押せる形（ボタン）にする: 人間が「消す」を選んだ。新しい purpose も要る（ADR-0013 決定8）ので不採用。
- ADR-0013 を supersede: 方針・メニュー用 purpose などは有効なまま。不採用。

## 帰結

- 実装（別の起草・PR）: `home.html` から要素と CSS を外す。`tests/test_authentication.py`・
  `tests/acceptance/dsl/authentication_browser.py`・`authentication-acceptance-review.md` に ⓘ を見る記述がある
  （本ADRでは触らない）。
