---
id: 0006
scope: project/dining-radar
status: 承認済み
date: 2026-08-01
approved_by: "本PRのマージをもって承認（ADR-0035 方式(i)、人間裁定 2026-08-01: 管理者作成の個別アカウント、公開サインアップなし、Django session、管理者支援のメールなしリセット）"
supersedes: []
superseded_by: null
relates_to: [P-01, P-02, P-03, P-04, P-07, P-08, P-09, TDR-AUTH-01, TDR-AUTH-02, TDR-AUTH-03, TDR-AUTH-04, TDR-AUTH-05, TDR-AUTH-06, TDR-AUTH-07, TDR-CS-00]
---

# ADR-0006: 招待制の Django session 認証で候補探索の公開境界を定める

> **承認者向けサマリ**: インターネットから利用できる幹事ツールにするため、候補探索は管理者が作成・無効化する個別アカウントだけに開放する。公開サインアップ、メールによるパスワードリセット、SSO は初期範囲に入れない。Django の same-origin session を使い、HTTPS、Secure/HttpOnly/SameSite cookie、CSRF、ログイン試行の抑制を公開境界として必須にする。この決定は認証を実装・デプロイするものでも、ホスト名や運用者向け画面を選ぶものでもない。

## 文脈

本アプリはランチ会の幹事が持ち回りで使うため、将来はインターネットから到達可能にする。一方、候補探索は非公開の runtime 検索基点と provider credential を server 側だけに持つ。ADR-0002 と ADR-0005 は、候補・地図・再提案を認証済みの幹事だけに返し、検索基点・provider 内部情報をブラウザへ出さないことを定めている。

Product Brief と現行 activeContext では、初期利用者を管理者が招待する個別アカウントとし、公開サインアップなし、ログイン・ログアウト・パスワード変更、管理者支援のメールなしリセット、アカウント無効化を求めている。具体的なホスト、ドメイン、メール配送、SSO、認証実装は未決である。このまま候補探索の実装へ進むと、既存 API の `organizerSession` と安全要件をどこで満たすかが曖昧になる。

## 決定

`contracts/authentication.feature` を受け入れ状態の SSOT、`contracts/authentication-api.md` を browser-facing の論理操作と runtime 設定境界の SSOT とする。候補探索 API の認証・CSRF 要件は、これらを参照して解釈する。

1. 認証方式は Django の same-origin session とする。候補探索・候補地図・再提案は、有効な個別幹事アカウントの session がある場合だけ利用できる。未認証、ログアウト済み、または無効化済みのアカウントは候補探索を利用できず、安全なサインイン案内または既存の `401 AUTHENTICATION_REQUIRED` を受ける。
2. アカウントは管理者が個別に作成し、無効化できる。公開サインアップ、共有アカウント、外部 IdP/SSO による自己登録は初期スコープから除く。無効化は、少なくとも次の保護リクエストから候補探索の利用を止める。
3. 利用者はログイン、ログアウト、認証済みのパスワード変更を行える。パスワードを忘れた利用者には、管理者が支援して reset する。公開の「パスワードを忘れた」要求、メール配送、メール内 reset token は初期版に置かない。reset の具体的な管理画面・一時パスワード方針は実装スライスで決める。
4. 外部公開時の browser session は HTTPS でだけ扱う。session cookie は `Secure`、`HttpOnly`、かつ明示した `SameSite` 方針（`Lax` 以上の制限）を持つ。cookie 名、session 有効期限、正確な `SameSite` 値、HTTP から HTTPS への遷移方法は、この境界を満たす実装・運用スライスで決め、公開リポジトリに実運用値を固定しない。
5. cookie 認証により状態を変える browser request は CSRF 保護を必須にする。候補再提案の `POST /candidate-proposals`、ログアウト、パスワード変更、ログイン form を含む。browser-facing API は同一オリジン利用を前提とし、credential を伴う任意 origin の CORS 利用、token を URL・local storage・公開設定へ置く方式は採用しない。
6. ログイン失敗試行は、アカウントの有無を漏らさない応答で抑制する。回数・時間窓・一時停止の具体値、復旧手順、監視先は実装と運用の判断に残すが、候補探索の provider rate limit とは別の境界として検証する。
7. 公開リポジトリには実アカウント名、メールアドレス、password hash、session・CSRF secret、cookie signing key、実運用 origin、allowlist、ログイン履歴を置かない。管理操作・認証失敗・保護 API の観測可能な出力も、非公開検索基点、credential、provider URL/response/ID を含めない。

## 検討した代替案

- **公開サインアップ**: 幹事の小規模な招待利用に不要であり、アカウント濫用・本人確認・回復導線の運用を増やすため採用しない。
- **メールで自己完結する password reset**: メール配送、送信元、token 保護、到達性を今決める必要があるため採用しない。初期は管理者支援に限定する。
- **bearer token または browser local storage の token 認証**: Django session と same-origin CSRF の既存候補探索契約から外れ、token の露出面を増やすため採用しない。
- **SSO を先に選ぶ**: 少人数の幹事利用には過剰であり、IdP・ドメイン・運用管理者を未決のまま固定するため後続スライスへ送る。
- **候補探索を未認証で公開する**: 非公開検索基点を保持する server-side provider call の悪用面を広げるため採用しない。

## 帰結

- 後続の実装は Django session と CSRF を候補探索 API の前提として実現し、認証の安全要件を合成データと設定検証で確認する。live provider credential や実アカウントを使うテストはしない。
- 候補探索の authorization は「有効な幹事 account の session」で判定し、見た目だけで未認証状態を隠す実装では代替しない。
- ログイン UI、管理 UI、ホスティング、ドメイン、メール配送、SSO、session 有効期限、password policy、throttle 数値はここで固定しない。これらを選ぶ変更は、実装または公開運用スライスで別途レビューする。
- ADR-0002 の公開リポジトリ・provider データ境界、ADR-0005 の候補探索 API・地図境界は継続して支配する。
