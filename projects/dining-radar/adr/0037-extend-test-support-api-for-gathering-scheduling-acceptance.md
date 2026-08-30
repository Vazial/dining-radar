---
id: 0037
scope: project/dining-radar
status: 提案中
date: 2026-08-30
approved_by: null
supersedes: []
superseded_by: null
relates_to: [P-01, P-02, P-05, P-07, P-08, P-10, P-11, ADR-0008, ADR-0023, ADR-0025, ADR-0034, ADR-0035, ADR-0036]
---

# ADR-0037: `test-support-api.yaml` をTDR-GTH（会の作成と日程調整）の受け入れ検証向けに拡張する

> **承認者向けサマリ**: `ADR-0035`・`ADR-0036`が起こしたTDR-GTH-01〜20の受け入れ契約
> （`gathering-scheduling.feature`）・API契約・browser-interface契約は、tester がL4を書くための
> 決定的なGiven状態の手段（`test-support-api.yaml`）をまだ持っていなかった（`ADR-0035`未決事項2・
> `ADR-0036`未決事項1で繰り返し持ち越されていた）。本ADRはこの拡張を行う。
>
> 本ADRは人間が個別にチャットで裁定した論点を含まない——今回の拡張は、既に承認済みの
> `ADR-0034`〜`0036`が定めた契約の上に、acceptance層の技術的な検証手段を設計する作業である。
> したがって`status: 提案中`のまま起草する（`meta/adr/0035`方式(ii)。判断材料は残すが、承認は
> 本PRのレビューを経て別途行う）。
>
> **決定は5点**。(1) 会・候補日・参加者リンク・出欠回答のGiven状態は、新しいtest-support seamを
> 追加せず、`gathering-scheduling-api.yaml`の公開境界（`createGathering`等）を直接呼んで構築する
> ——TDR-GTHの資源はTDR-AUTHと違い、すべて公開APIから作成できるため。(2) 有効期限90日・レート
> 制限の**具体的な閾値が正しいかどうか**はL1（developerの単体テスト）の責務とし、本ファイルの
> 新設2seam（`seedExpiredParticipantLink`・`seedRateLimitedParticipantLink`）は**期限切れ／
> レート制限時の挙動**だけをL4で決定的に検証する。(3) 「その日に開いている店」の母集団は、
> `gathering-scheduling-api.yaml`自身が明記するとおりcandidate-searchと共有される母集団であるため、
> 新しいエンドポイントを立てず既存の`setCandidateProposalAcceptanceState`に新しいmode
> （`GATHERING_OPEN_SHOP_WEEKDAY_MATCH`）を追加する形で相乗りする。(4) 署名付きリンクのtokenは、
> 公開APIの発行応答からそのまま読み取って使う——test-support側でtokenを予測可能にする、または
> 固定するという設計は採らない。(5) `resetGatheringSchedulingAcceptanceState`を新設し、既存の
> TDR-AUTH・TDR-CSそれぞれの独立したreset seamと同じ設計に倣う。

## 文脈

### 1. 何が起きたか

`ADR-0035`は`gathering-scheduling.feature`・`gathering-scheduling-api.yaml`を、`ADR-0036`は
`gathering-scheduling-browser-interface.yaml`（発行済みリンクの一覧・再コピー・失効を含む）を
起草した。両ADRとも「`test-support-api.yaml`のTDR-GTH向け拡張は本ADRでは着手していない」と明記し、
次工程へ送っていた（`ADR-0035`未決事項5、`ADR-0036`未決事項1）。PR #177で第1弾のbrowser契約・
API v0.2.0が承認され、testerがL4シナリオを書く段になり、この最後の契約ピースが必要になった。

### 2. TDR-AUTH・TDR-CSとの構造的な違い

`test-support-api.yaml`が既に持つseamは、いずれも**公開境界だけでは作れない状態**のために存在する。
TDR-AUTHは公開サインアップが無い（`setAuthenticationAcceptanceAccount`が無ければアカウントを
一切作れない）。TDR-CSは非公開の外部provider（Hot Pepper）に依存する母集団を持つ
（`setCandidateProposalAcceptanceState`が無ければ決定的な候補データを一切作れない）。

TDR-GTHはこの2つと事情が異なる。会・候補日・参加者リンク・出欠回答は、いずれも
`gathering-scheduling-api.yaml`自身の公開操作（`createGathering`・`addCandidateDate`・
`issueParticipantLinks`・`setScheduleResponse`・`setParticipantDisplayName`・
`confirmCandidateDate`・`revokeParticipantLink`・`recopyParticipantLink`・
`listParticipantLinks`）だけで作成できる——外部providerにも、公開されていない管理操作にも依存
しない。したがって`meta/verification.md`のL4詳細が定める「状態の準備・検証はSUTの公開境界経由で
行う。DB直接操作はGiven専用のseamとして明示的に定義した箇所のみ許可」という原則に従えば、TDR-GTHの
大半のGivenには新しいseamを追加しないことが正しい。

例外は3つに絞られる。

1. 参加者リンクの**有効期限切れ**（TDR-GTH-14）。90日という実際の経過時間を受け入れテストで
   待つことはできない。
2. 参加者リンクの**レート制限**（TDR-GTH-15）。実際の閾値に達するまで大量にリクエストを送る
   方式は、時間依存・環境依存で不安定になる（`meta/verification.md` 3.4が走破的な手段を回帰
   ゲートに使わないよう戒めるのと同じ理由）。
3. 「その日に開いている店」（TDR-GTH-08・09）が依拠する母集団は、公開のcandidate-search境界
   からしか制御できない——ただしこれは**新しいTDR-GTH固有のseamではなく、TDR-CSが既に持つ
   seamの拡張**で足りる（決定3）。

## 決定

### 決定1. Given状態は原則として公開境界経由で構築し、新しいseamを最小化する

会・候補日・参加者リンク（発行・失効・再コピー）・出欠回答（名前の有無を含む）のGivenは、
`gathering-scheduling-api.yaml`の公開操作を直接呼んで組み立てる。TDR-GTH-01・02・03・04・05・
06・07・10・11・12・13・16・17・18（の大部分）・19・20は、この方針だけで実現できる——本ADRは
これらのために新しいtest-support操作を1つも追加しない。

TDR-GTH-13（トークンの推測）も同様に、公開境界だけで検証できる——発行済みトークンとは異なる
任意の文字列を組み立て、公開の参加者ビューへ渡して`LINK_NOT_FOUND`を確認すればよく、専用seamは
不要である。

### 決定2. 有効期限・レート制限は「挙動」をL4で、「閾値の正しさ」をL1で検証する

`seedExpiredParticipantLink`・`seedRateLimitedParticipantLink`を新設する。いずれも
`seedThrottledSignInAttempt`（TDR-AUTH-07）と同じ設計方針を踏襲する——**実際の閾値・経過時間を
一切公開しない**。90日という具体的な日数、レート制限の具体的な閾値（`ADR-0035`決定4が「根拠の
薄い値」と明記した数値）そのものが正しく設定されているかどうかは、本ファイルの関与しない範囲と
する。

`meta/verification.md`の段構造に沿って、次のように割り当てる。

- **L1（developerの単体テスト）**: 実装が採用した設定値（有効期限日数、レート制限の閾値）が
  意図した値と一致することを、実際の設定・定数に対する単体テストで検証する。
- **L4（本ファイルのseamを使った受け入れテスト）**: 期限切れ・レート制限に**達した場合の挙動**
  （`LINK_EXPIRED`/`LINK_RATE_LIMITED`が返る、既存の回答・タリーが保持される）を、実際の日数や
  リクエスト数を再現せずに決定的に検証する。

この分担は、TDR-CSの`RATE_LIMITED`/`RATE_LIMITED_AFTER_INITIAL_SUCCESS`モードが既に採用している
考え方（具体的な閾値を検証対象にせず、閾値に達した後の挙動だけを決定的に作る）の再利用である。

### 決定3. 「その日に開いている店」の母集団は、TDR-CSの既存seamに相乗りする

`gathering-scheduling-api.yaml`は、`previewOpenShopsForCandidateDate`・
`ParticipantScheduleQuestion.openShopCount`が「candidate-search-api.yamlと同じ非公開検索基点の
母集団」を参照すると明記している。本番のパイプラインが母集団を共有しているのだから、acceptance
seamも同じ1つの制御経路（`setCandidateProposalAcceptanceState`）を共有すべきであり、TDR-GTH専用の
別のエンドポイントを新設しない。

`CandidateProposalAcceptanceState.mode`へ`GATHERING_OPEN_SHOP_WEEKDAY_MATCH`を追加する。既存の
全モードが共有する合成母集団ファクトリ（`src/dining_radar/suggestions/acceptance_state.py`の
`_synthetic_candidate`）は、`regularHoliday`を一律`"日曜・祝日"`に固定しており、TDR-CSの目的
（`regularHoliday`の**文字列自体を業務ロジックが読むことはない**）には十分だが、TDR-GTHの曜日
照合（`ADR-0035`決定6）を複数の曜日・複数トークン・不定休・null（未確認）にわたって検証するには
不足する。新設モードは6件の合成候補（月曜のみ閉店・水曜のみ閉店・火曜と水曜の両方閉店・日曜閉店
[既存と同じ文字列]・不定休・regularHoliday省略）を持ち、候補日の曜日ごとに厳密な既知件数
（月5/火5/水4/木6/金6/土6/日5）を返す。既存モードの挙動、既存TDR-CSシナリオの観測結果は一切
変えない——追加のみである。

曜日照合アルゴリズム自体の網羅的な単体検証（「水曜以外」のような否定表現を含む限界事例）は、
決定2と同じ理由でL1の責務とする——本seamは母集団からAPI応答への配線を代表的な数ケースで
決定的に検証するにとどめる。

### 決定4. トークンはseam側で予測可能にせず、公開APIの応答からそのまま使う

`seedExpiredParticipantLink`・`seedRateLimitedParticipantLink`はいずれも、**既に公開の
`issueParticipantLinks`/`recopyParticipantLink`が返したtoken**を入力として受け取る
（`ParticipantLinkTokenSeed`）。test-support側でtoken値を生成・予測可能にする、またはacceptance
専用の固定値を割り当てるという設計は採らなかった。

理由は、本番のトークン生成経路（`ADR-0035`決定4が要求する推測不能性）を、acceptance用にだけ
弱めたり分岐させたりする理由が無いためである。token生成ロジック自体はacceptance環境でも本番と
同じコードパスを通ってよく、通す方が「本番と異なるコードパスをテストする」という別のリスクを
避けられる。この設計は、認証境界のtest-supportが「パスワードは受け取った値をそのまま使える
必要がある（`AcceptanceAccountState.password`）」としつつ、パスワードのハッシュ化・照合ロジック
自体は本番と同じ経路を通すのと同型である。

### 決定5. `resetGatheringSchedulingAcceptanceState`を新設する

TDR-AUTH・TDR-CSそれぞれが独立したreset操作（`resetAuthenticationAcceptanceState`・
`resetCandidateProposalAcceptanceState`）を持つのと同じ設計で、TDR-GTH専用のreset操作を新設
する。会・候補日・参加者リンク（失効・レート制限・期限切れの seed 状態を含む）・出欠回答を
まとめて削除し、他の2ドメイン（認証・候補提案）には触れない。

## 検討した代替案

- **会・候補日・リンク・回答の生成にも専用seamを新設する（DB直接操作）**: 却下。
  `meta/verification.md`が「DB直接操作はGiven専用のseamとして明示的に定義した箇所のみ許可」と
  定めており、これらはすべて公開境界から作れるため、専用seamを設ける根拠が無い（P-05: 要るように
  なってから足す）。
- **有効期限・レート制限の実際の閾値をtest-support-api.yamlに含め、L4がその値を使って実時間・
  実リクエスト数で検証する**: 却下。90日を実際に待つことも、レート制限の実閾値まで実際に
  リクエストを送ることも、L4の実行時間・安定性を著しく損なう。`seedThrottledSignInAttempt`の
  既存の設計判断（閾値を露出しない）をそのまま踏襲するほうが一貫している。
- **TDR-GTH専用の母集団制御エンドポイントを新設する（TDR-CSのseamとは別立て）**: 却下。本番の
  パイプラインが母集団そのものを共有している以上、2つの独立した制御経路を持つと、両者が食い違う
  （例えば同じmodeでもTDR-CS側とTDR-GTH側で異なる母集団を返す）というバグの温床になる。1つの
  経路に統合するほうが安全である。
- **署名付きリンクのtokenをtest-support側で固定・予測可能な値に差し替えられるようにする**: 却下。
  本番のトークン生成・検証ロジックをacceptance環境だけ迂回させることになり、「acceptanceで緑でも
  本番のトークン生成が壊れていれば気づけない」という種類のリスクを生む。

## 帰結

- `contracts/test-support-api.yaml`（更新、`version` 1.4.0→1.5.0、ステータス: 承認待ち）に、
  `resetGatheringSchedulingAcceptanceState`・`seedExpiredParticipantLink`・
  `seedRateLimitedParticipantLink`と、`CandidateProposalAcceptanceState.mode`への
  `GATHERING_OPEN_SHOP_WEEKDAY_MATCH`追加、新規スキーマ`ParticipantLinkTokenSeed`を反映した。
- `gathering-scheduling.feature`・`gathering-scheduling-api.yaml`・
  `gathering-scheduling-browser-interface.yaml`はいずれも変更していない——本ADRはacceptance層の
  検証手段だけを追加する。
- 既存のTDR-AUTH・TDR-CS向けのmode・seam・reset操作の挙動・観測結果は一切変更していない
  （追加のみ）。
- `ADR-0035`未決事項5・`ADR-0036`未決事項1（`test-support-api.yaml`のTDR-GTH向け拡張）はこれで
  果たされた。
- `design/explorations/**`・`ARCHITECTURE.md`・`design.md`は変更しない——test infrastructure層の
  拡張にとどまる。

## 未決事項（次工程への申し送り）

1. **本ADR自体の承認**: `status: 提案中`のまま起草した。人間が本PRをレビューし、差分が
   意図どおりであることを確認した時点で`承認済み`へ格上げする（`meta/adr/0064`決定1の書式）。
2. **`GATHERING_OPEN_SHOP_WEEKDAY_MATCH`の6件の合成候補の緯度値・genre値の具体的な数値**は本ADR・
   契約では固定しない——`WALKING_TIME_LIMIT_EXCLUDES`等の既存モードと同じく、実装（developer）が
   `acceptance_state.py`にどのような具体的な緯度・ジャンル文字列を割り当てるかは実装裁量である。
3. **`ADR-0035`・`ADR-0036`から持ち越されたまま**: 会データの保持期間・削除方針、署名付き
   リンクの具体的な有効期限日数・レート制限閾値そのものの妥当性（根拠の薄い暫定値）、承認投票・
   確定スライスのための`test-support-api.yaml`拡張（本ADRは第1弾のみを対象とする）。
