# Toyama Dining Radar acceptance contract — TDR-AUTH authentication and public access
#
# Status: this contract becomes durable when the active authentication-boundary
# PR merges under ADR-0035 approval mode (i). It does not authorize an
# implementation or a deployment.

Feature: 招待された幹事だけがインターネット越しに候補探索を利用する
  持ち回りの幹事は、管理者が作成した自分のアカウントでサインインし、
  非公開の検索基点を見ずに候補を比較する。公開サインアップやメールを
  使う自己回復は提供せず、管理者がアカウントと reset を支援する。

  # TDR-AUTH-01
  Scenario: 未認証の訪問者は候補探索を利用できない
    Given 訪問者は有効な幹事 session を持たない
    When 訪問者が候補提案画面または候補提案 API を開く
    Then 訪問者はサインインするよう安全に案内される
    And 候補、地図、再提案の切り口、非公開の検索基点は示されない
    And API は候補提案契約どおりの AUTHENTICATION_REQUIRED を返せる

  # TDR-AUTH-02
  Scenario: 管理者が作成した個別アカウントで候補探索を始める
    Given 管理者が幹事の個別アカウントを有効にしている
    When 幹事が正しい認証情報でサインインする
    Then same-origin の認証済み session が開始される
    And 幹事は候補提案画面を開ける
    And 幹事は自分の認証情報を他の利用者と共有するよう求められない

  # TDR-AUTH-03
  Scenario: 公開サインアップとメールによる自己回復を提供しない
    Given 訪問者またはパスワードを忘れた幹事がいる
    When その人がアカウント作成またはメールによる password reset を求める
    Then 公開のサインアップは利用できない
    And reset 用メールまたはメール内 token は送られない
    And 幹事には管理者に支援を依頼する経路だけが案内される

  # TDR-AUTH-04
  Scenario: 幹事はサインアウトとパスワード変更を行える
    Given 幹事は有効な session でサインインしている
    When 幹事がサインアウトする
    Then その browser session では候補探索を続けられない
    When 幹事が認証済みでパスワードを変更する
    Then 以後のサインインは変更後の認証情報で行える

  # TDR-AUTH-05
  Scenario: 管理者の無効化は保護された候補探索を止める
    Given 幹事は候補探索を利用できる session を持っている
    When 管理者がそのアカウントを無効化する
    Then 以後の保護された候補探索 request は認証済み幹事として扱われない
    And 候補、地図、再提案の切り口、非公開の検索基点は返されない

  # TDR-AUTH-06
  Scenario: 公開 browser session の transport と state change を保護する
    Given インターネットから利用できる環境に認証機能が配置されている
    When browser が session を開始する、または cookie 認証で状態を変える request を送る
    Then session は HTTPS と Secure、HttpOnly、SameSite cookie 方針で扱われる
    And 状態を変える request は有効な CSRF 保護なしに受け付けられない
    And credential を伴う任意 origin の CORS や browser local storage の認証 token は使われない

  # TDR-AUTH-07
  Scenario: 失敗したサインインを抑制しアカウントの有無を漏らさない
    Given 訪問者が短時間に失敗したサインインを繰り返している
    When 訪問者がさらにサインインを試みる
    Then login 試行は抑制される
    And 応答はアカウントの有無または無効化状態を明かさない
    And 非公開の検索基点、credential、provider 内部情報は明かされない
