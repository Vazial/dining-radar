# Toyama Dining Radar acceptance contract — TDR-CS candidate proposals
# ステータス: 承認済み(2026-08-09) — 人間が2026-08-09のチャットで実データのフィールド調査を踏まえた
#   所感（「近さ・ジャンル・禁煙は良い切り口」「総席数・予算感・カード払い可否は加工すれば参考情報として
#   使える」)を示し、architectがこれをTDR-CS-02の改訂（アクセスを外し、総席数・禁煙対応・予算感を
#   目安表現にする）と新規TDR-CS-12（カード払い不可の注意）へ翻訳した（adr/0019）。予算感は当初の
#   ドラフトで全面却下されたが、その却下理由の一部が循環していたことが判明し、人間が「ざっくりの段階
#   表示ができるなら入れてほしい」と再確認・差し戻したため、TDR-CS-02へ追加した（adr/0019決定8）。
#   他のシナリオは2026-08-08改訂（adr/0016・adr/0017）からの変更なし——切り口(ConceptKind)の中身の
#   組み替えは、この契約がコンセプトの具体名を書いていないため文言変更を要しない。承認の実体は本PRの
#   マージである。変更には再承認が必要。この行の形式は meta/adr/0043 の機械検証が要求する
#
# Status: human content-approved in chat (2026-08-03 amendment; original
# approval 2026-08-01) and made durable by merged PR #76. TDR-CS-09 and
# TDR-CS-10 are a 2026-08-07 addition (adr/0015). TDR-CS-11 is a 2026-08-08
# addition (adr/0016) reflecting a real-device review that found one
# comparison lens (removed from the underlying contract) produced no
# observable difference from the initial one, and replaced it with a
# same-lens "try again" action. TDR-CS-02 was amended again the same day
# (adr/0017, a third real-device review) to drop business hours from the
# required card fields. TDR-CS-02 was amended a second time on 2026-08-09
# (adr/0019, a field survey of the same live candidates) to drop access from
# the required card fields and to describe total seats and non-smoking
# status as coarse references rather than exact/raw values; TDR-CS-12 is a
# 2026-08-09 addition (adr/0019) for the card-level card-payment caution.
# TDR-CS-02 was amended a third time the same day (adr/0019 decision 8,
# after a same-day human re-confirmation reversed an initial rejection) to
# add a coarse dinner-budget reference, explicitly disclosed as a dinner
# figure. No other scenario text changed.

Feature: 幹事がランチ候補を見て別の切り口で比べ直す
  幹事は非公開の検索地点の周辺にあるランチ候補を、選ぶ理由の異なる
  切り口で比較する。サインイン後は最初の候補と位置関係をすぐ見て、
  合わないときだけ別の切り口を選んで提案を作り直す。候補を固定件数ずつ
  増やすことはしない。

  Background:
    Given 非公開の検索地点が登録されている
    And 出典の表示と詳細への導線を利用できる
    And 幹事はサインインしている

  # TDR-CS-00
  Scenario: サインインしていない訪問者には候補提案を見せない
    Given 訪問者はサインインしていない
    When 訪問者が候補提案画面を開く
    Then 訪問者はサインインするよう案内される
    And 訪問者は再提案の切り口、店舗カード、地図、補助条件を見られない

  # TDR-CS-01
  Scenario: サインイン後に初期のランチ候補と位置関係をすぐ比較する
    Given ランチ営業の候補を提案できる
    When サインイン済みの幹事が候補提案画面を開く
    Then 初期の切り口に基づく候補とその地図が示される
    And 初期表示で幹事に補助条件またはコンセプトの選択を求めない
    And 初期の切り口には選ぶ理由が示される
    And 初期の候補に同じ店舗は重複して示されない
    And 非公開の検索地点や探索条件の詳細は示されない
    And 出典の表示と詳細へのリンクが示される

  # TDR-CS-02
  Scenario: 選んだコンセプトの店舗を地図とカードで比較する
    Given 幹事に一つの切り口による候補が示されている
    When 幹事が候補を比較する
    Then その切り口の店舗がカードと地図に示される
    And 店舗カードを選ぶと対応する地図上の店舗が強調される
    And 地図上の店舗を選ぶと対応する店舗カードが強調される
    And 地図は示されている店舗が見渡せる範囲になる
    And 店舗カードには店名、ジャンル、紹介、定休日、総席数のめやす、禁煙対応のめやす、予算のめやす、詳細へのリンクが示される
    And 予算のめやすは、ディナーの価格であることが分かるように示される
    And 非公開の検索地点、経路、現在地、徒歩時間は示されない
    And 地図の出典表示が示される

  # TDR-CS-03
  Scenario: 次のページを足さずポップアップで別の切り口を選んで再提案する
    Given 幹事に一つの切り口による候補が示されている
    When 幹事が「別の切り口で再提案」を選ぶ
    Then 再提案に使える切り口が3つ以下のポップアップで示される
    And 現在表示中の切り口は再提案の選択肢に含まれない
    And 幹事が一つの切り口を選ぶと新しい候補提案が依頼される
    And 新しい提案は選んだ切り口の候補と地図を示す
    And 以前の提案に候補を追加しない
    And 同じ画面で既に表示した店舗は未表示の店舗より後ろに表示される
    And 既に表示した店舗も候補から除外されない
    And 新しい提案が以前とすべて異なる店舗になるとは限らない

  # TDR-CS-04
  Scenario: 補助条件なしで切り口による比較を保つ
    Given ランチ営業は必須である
    When 幹事が候補提案画面を開く、または再提案の切り口を選ぶ
    Then 幹事は検索範囲の希望またはジャンルを入力・選択しない
    And 幹事は初期候補を比較するか、再提案のときだけ切り口を選ぶ
    And 幹事は並び順を手動で指定できない

  # TDR-CS-05
  Scenario: 条件に合うランチ候補がない
    Given 選んだ切り口で提案できるランチ営業の店舗がない
    When 幹事が候補提案画面を開く、または再提案の切り口を選ぶ
    Then 条件に合う候補がないことが示される
    And 情報を取得できなかった場合とは区別して示される

  # TDR-CS-06
  Scenario: 候補情報を取得できない
    Given 候補情報を今は取得できない
    When 幹事が候補提案画面を開く、または再提案の切り口を選ぶ
    Then 幹事には後で試すよう安全に案内される
    And 非公開の検索地点や内部の事情は示されない

  # TDR-CS-07
  Scenario: 対応していない再提案の切り口を選んだ
    Given 幹事が現在提示されていない切り口を選んでいる
    When 幹事が再提案を依頼する
    Then その切り口では提案できないことが示される
    And 非公開の検索地点や探索条件の詳細は示されない

  # TDR-CS-08
  Scenario: 短時間に提案を繰り返し依頼した
    Given 幹事が短時間に候補提案を繰り返し依頼している
    When 幹事が候補提案画面を開く、または再提案の切り口を選ぶ
    Then 幹事には少し待ってから試すよう案内される
    And 非公開の検索地点や内部の事情は示されない

  # TDR-CS-09
  Scenario: 居酒屋やバーなどランチ営業が確認しづらい候補は、既定では外し、選べば含める
    Given 提案できる候補に、ランチ営業の実施が確認しづらいジャンルの店舗が含まれている
    When 幹事が候補提案画面を開く
    Then 初期の候補にはランチ営業の実施が確認しづらいジャンルの店舗を含めない
    And 幹事は「居酒屋・バーを含めて探す」といった切り口を再提案の選択肢として選べる
    And 幹事がその切り口を選ぶと、選んだ切り口の候補にはランチ営業の実施が確認しづらいジャンルの店舗も含まれる
    And その切り口の説明は、含めた店舗が実際にランチ営業していると断定しない

  # TDR-CS-10
  Scenario: 除外すると候補が一つもなくなる場合は、除いていた店舗も含めて示す
    Given ランチ営業の実施が確認しづらいジャンルを除くと提案できる候補が一つもない
    And そのジャンルを含めれば提案できる候補がある
    When 幹事が候補提案画面を開く
    Then 除いていたジャンルの店舗も含めた候補が示される
    And 「条件に合う候補がない」という案内は、そのジャンルを含めても候補が一つもないときだけ示される

  # TDR-CS-11
  Scenario: 同じ切り口のまま「もう一度探す」を選ぶ
    Given 幹事に一つの切り口による候補が示されている
    When 幹事が「もう一度探す」を選ぶ
    Then 同じ切り口で新しい候補提案が依頼される
    And 新しい提案は同じ切り口の候補と地図を示す
    And 以前の提案に候補を追加しない
    And 同じ画面で既に表示した店舗は未表示の店舗より後ろに表示される
    And 既に表示した店舗も候補から除外されない
    And 新しい提案が以前とすべて異なる店舗になるとは限らない

  # TDR-CS-12
  Scenario: カード払いができない候補には注意が示される
    Given 候補にカード払いができない店舗が含まれている
    When 幹事が候補を比較する
    Then カード払いができない店舗のカードには、その旨の注意が示される
    And カード払いができる、または情報がない店舗にはこの注意が示されない
