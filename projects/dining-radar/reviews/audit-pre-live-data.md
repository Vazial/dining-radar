# 監査レポート: toyama-dining-radar 実データ運用前の契約・モデル・アーキテクチャ整合性監査

- 作成: architect
- 監査対象: `product-brief.md`・`design.md`・`ARCHITECTURE.md`・`friction-log.md`（FR-001〜FR-008）・
  `adr/0001`〜`0013`（全13本）・`contracts/**`（`.feature` 2本、`*-api.yaml` 2本、
  `*-browser-interface.yaml` 2本、`test-support-api.yaml`）・`src/**`・`tests/**`・`env.example`・
  `pyproject.toml`・`reviews/audit-tdr-cs.md`・`design/reconciliation/**`・`design-briefs/**`・
  `design-preview/**`・`.github/workflows/ci-toyama-dining-radar.yml`
- 権限上の制約: architectはBashを持たない。以下は**すべて `Read`/`Grep`/`Glob` による静的な突き合わせ**であり、
  CI・テストスイートを自分で実行したものは1件もない。「実行して緑を確認した」という記述はどこにもない
  ——orchestrator/reviewerの既存申告（L0〜L4全緑、L4 15件skipゼロ）を**そのまま信頼しており、独立に再実行して
  いない**（meta/adr/0039）。契約ファイル同士・契約とソースコードの文字列レベルの一致/不一致は、
  読んだ内容の突き合わせとして高い確度がある

---

## 0. 承認者向けサマリ

**結論: 条件付きでOK。ブロッキングではないが、実データ運用に進む前に対処を推奨する具体的な欠陥を1件、
実データ運用の意味を狭める既知の制約を1件、新たに発見した。**

1. **【新規発見・非ブロッキング】L4契約とL4テストのドリフト**: ADR-0013で`candidate-search-browser-interface.yaml`が
   `allowedPurposes`に`auth-account-menu-toggle`を追加したが、L4アクセプタンステストのハードコードされた
   許可リスト（`tests/acceptance/dsl/candidate_search_browser.py`の`ALLOWED_CONTROL_PURPOSES`）は
   更新されておらず、しかもこの新しいコントロール（`<summary>`要素）はテストの走査セレクタ
   （`FORM_CONTROL_SELECTOR`）にそもそも引っかからない。結果、ADR-0013が「意図通り機能している証拠」と
   評価した許可リストの安全弁が、その根拠となった当のコントロールに対しては**一度も実行されていない**。
   実害は今のところ無い（developerが正しいpurpose文字列を自発的に付けている）が、TDR-CS-07で
   reviewerが見つけたのと同型の「緑だが検証していない」欠陥である。詳細は1節
2. **【新規発見・非ブロッキング】`Referrer-Policy`の実装値がADR-0008/ARCHITECTURE.mdの決定文と異なる**:
   ADRは公開運用で`strict-origin-when-cross-origin`を明記するが、`settings_base.py`は
   `same-origin`を設定しており、どのテストも検査していない。実害の方向性は「より厳しい」側（OSMへの
   Refererが一切送られない）だが、決定文と実装が無断で食い違っている。詳細は2節
3. **【既知・再確認のみ】Hot Pepperの生フィールド名の仮定は合成fixtureでしか検証されていない**
   （ADR-0002決定7が生の資格情報テストを禁じているため構造的に不可避）。実キーを入れて動かす作業
   そのものが、この再確認の機会になる。ただし`normalize.py`の欠損値処理は「値が無ければ`None`」という
   寛容な設計であるため、**フィールド名の想定が外れても例外は飛ばず、該当項目が黙って「情報なし」に
   なるだけ**という点を認識しておくこと。詳細は3節
4. **実データ運用の意味を狭める制約（既知・disclosure）**: デプロイスライスが未着手（ADR-0042）であり、
   `SECURE_SSL_REDIRECT`は実TLS終端を前提にしている。したがって「実データで動かす」は**当面ローカル・
   非公開環境での稼働に限られ**、インターネット公開を意味しない。これは欠陥ではなく、ADR-0007/0042が
   既に明示的にスコープ外としている事実の再確認である
5. 契約どうし・契約とADR・契約と実装の突き合わせでは、上記2件を除き**差し戻しレベルの矛盾は見つからなかった**。
   13本のADRは相互に矛盾せず、supersede関係（0004→0005）も正しく機能している

以下、観点別に記す。

---

## 1. 契約どうしの整合、契約と実装の整合、契約と検証の整合

### 1.1 主要な整合性は良好

- `.feature`（TDR-CS-00〜08、TDR-AUTH-01〜07）↔ `*-api.yaml`（candidate-search-api.yaml v0.4、
  authentication-api.md）↔ `*-browser-interface.yaml`（v0.3、v0.2）↔ 実装（`web/views.py`・
  `web/serializers.py`・`candidate.js`・`home.html`）を突き合わせた結果、フィールド名・enum値・
  HTTPステータス・ProblemResponseコード・total-seatsの`data-raw-value`例外（ADR-0011）・
  `allowedPurposes`の大半（後述の1件を除く）は一致している。`serializers.py`は
  `additionalProperties: false`のスキーマに対しフィールドを過不足なく生成しており、
  `candidate-search-api.yaml`のenum・required配列とも一致する
- `test-support-api.yaml`の seam は `test_support/urls.py` → `acceptance_urls.py` 経由で
  `ACCEPTANCE_TEST_SUPPORT`フラグ配下にのみ登録され、`tests/test_test_support.py`が
  「フラグがFalseなら404」を明示的に検証している。契約が要求する「本番・開発では登録されない」という
  境界は機械的に閉じている
- `reviews/audit-tdr-cs.md`が独立に発見・解消したTDR-CS-07の「緑だが検証していない」欠陥は、
  現在のコード（`request_unsupported_lens_directly`）を読む限り実際に解消されている
  （UI操作で実際に送信し、ネットワークレベルで本文だけ差し替える方式に変更済み）

### 1.2 【新規発見】`auth-account-menu-toggle`購入がL4で一度も検査されていない

**事実関係（すべて`Read`で確認）:**

- `contracts/candidate-search-browser-interface.yaml`（v0.3、ADR-0013）の`allowedPurposes`は
  9値——`auth-account-menu-toggle`を含む——である（157行目）。契約は
  `allCandidateScreenFormControlsMustDeclarePurpose: true`を明記し、「test idの有無を問わず
  候補提案画面上の全フォームコントロールがpurposeを宣言し、そのpurposeが許可リストに含まれること」
  を要求している
- 実装（`src/dining_radar/web/templates/web/home.html` 321〜326行）は、パスワード変更・サインアウトを
  束ねる`<details><summary>`ディスクロージャに`data-testid="auth-account-menu-toggle"`・
  `data-candidate-control-purpose="auth-account-menu-toggle"`を正しく付与している
- しかし `tests/acceptance/dsl/candidate_search_browser.py` の
  `ALLOWED_CONTROL_PURPOSES`（124〜133行）は**8値のまま**——`auth-account-menu-toggle`を含まない
  ——契約v0.3が要求する許可リストと同期していない
- さらに、同ファイルの`FORM_CONTROL_SELECTOR`（144〜158行）は
  `select, input:not([type='hidden']), textarea, button, [role='checkbox'], [role='radio'],
  [role='range'], [role='combobox'], [role='listbox'], [role='slider'], [role='spinbutton']`
  という固定セレクタであり、**`summary`タグも`[role='button']`も含まれていない**。
  `<summary>`要素はHTML-ARIAの仕様上「button」相当の暗黙roleを持つが、実装は明示的な
  `role="button"`属性を付けていない（自然な`<details>`/`<summary>`ネイティブセマンティクスを
  意図的に選んだと`home.html`のコメントにある）。したがってこのコントロールは、
  `ALLOWED_CONTROL_PURPOSES`が更新されていたとしても、**そもそも走査対象に入らない**
- `grep`で確認した限り、`auth-account-menu-toggle`という文字列は`tests/`配下のどこにも出現しない
  （契約・ADR・`home.html`にのみ出現）。この画面（`candidate.js`／`home.html`）はvanilla JS・
  bundlerなし構成のため**L1単体テストが存在せず**（`tests/`にJSテストランナーは無い）、
  L4のブラウザ自動化がこのコントロールに対する唯一の機械検証層である。その唯一の層がこの
  コントロールに触れていない

**帰結**: `assert_no_secondary_conditions_or_manual_sort`（TDR-CS-01/04が使う）のコメントは
「pre-filter on data-candidate-control-purpose already being present」しないことで
「未宣言のコントロールが検査を逃れないように」していると明記しているが、この保証は
`FORM_CONTROL_SELECTOR`に載っていない要素には及ばない。今回は実害が無い
（developerが自発的に正しいpurposeを宣言したため）が、**もし将来同種のディスクロージャ
コントロールに`forbiddenPurposes`（`secondary-condition`・`filter`・`sort`・`manual-ordering`）
のいずれかが紛れ込んでも、この検査は気づかない**。ADR-0013決定5が「許可リストが意図通り機能している
証拠」として挙げたN-7予見は、契約起草側の予見であって、**L4側の検査が実際にその予見を執行できている
ことの証拠ではない**——両者は別の主張である。

**推奨（非ブロッキング。tester/developerの領分。architectは契約もテストコードも書き換えない）**:
1. `ALLOWED_CONTROL_PURPOSES`に`auth-account-menu-toggle`を追加し、契約v0.3と同期させる
2. `FORM_CONTROL_SELECTOR`に`summary`（または`<details>`直下の`<summary>`に限定するより厳密な
   セレクタ）を追加し、この種のネイティブディスクロージャコントロールも
   `allCandidateScreenFormControlsMustDeclarePurpose`の走査対象に含める
3. 副次的に、reviewerが`reviews/audit-tdr-cs.md`で既に指摘していた「`[role='button']`が
   走査対象に含まれない」という非ブロッキング事項も、今回のケースで実例を伴って顕在化したため、
   同じ修正の中でまとめて解消することを推奨する

この欠陥はブロッキングとは判定しない——認証・provider秘密・非公開検索基点のいずれの境界にも
関わらず、現在のマークアップは既に正しいpurposeを宣言している。しかし「検証していないことを
問題なしと報告してはならない」という規律（meta/adr/0039）に照らし、次にこの検査に触れる
tester/reviewerへの申し送りとして明記する。

---

## 2. `Referrer-Policy`の決定文と実装の不一致

- **ADR-0008決定5**: 「OSM 標準タイルへ適切な Referer を送るため、公開運用時の Referrer-Policy は
  クロスオリジンには origin だけを送る `strict-origin-when-cross-origin` とする」
- **ARCHITECTURE.md**（データと秘密の境界節）: 「Leaflet/OSM の公開運用は
  `Referrer-Policy: strict-origin-when-cross-origin` とし、タイル提供者へ公開 origin だけを送る」
- **実装**（`src/dining_radar/settings_base.py` 70行）: `SECURE_REFERRER_POLICY = "same-origin"`

`same-origin`は同一オリジン宛リクエストにはフルRefererを送るが、**クロスオリジン宛（OSMタイル
サーバ宛を含む）には一切Refererを送らない**——`strict-origin-when-cross-origin`（オリジンだけを送る）
とは異なる値である。方向としては「より情報を出さない」側の食い違いであり、非公開検索基点の露出という
Must要件には抵触しない。しかし:

- これは**決定済みのADR本文と「設計の現在」を映すはずのARCHITECTURE.mdの両方**が明記する値からの
  無断の逸脱であり、どちらのファイルもこの値を承知の上で改訂されたようには見えない（ADR-0010の
  Leafletベンダリング作業のコミット文脈でLeaflet配信元だけが変わった可能性がある）
  ——**architectはgit blameを実行できないため、原因は特定していない。事実の指摘に留める**
- どのテストもこの設定値を検査していない（`test_structure.py`はcookie/CSRF設定は検査するが
  `SECURE_REFERRER_POLICY`は検査していない）。したがってこの逸脱はCIでは今後も検出されない
- OSM Tile Usage Policyは通常、トラフィック識別のためにRefererヘッダの送出を推奨する運用がある
  （このプロジェクトはprovider規約の再確認を公開運用前の必須事項として既に自ら課している——
  design.md「後続スライスへの条件」）。`same-origin`のままだと、OSM側からは送信元不明のトラフィックに
  見える可能性があり、regular provider-terms reconfirmationの際にこの値も一緒に見直す必要がある

**推奨（非ブロッキング。人間の判断を伴う軽微な整合修正）**:
- 案A: 実装を`strict-origin-when-cross-origin`に修正し、ADR/ARCHITECTURE.mdの決定文どおりにする
- 案B: `same-origin`を意図した選択として追認し、ADR-0008・ARCHITECTURE.mdの記述を更新する
  （軽微だが、決定を後から書き換えるにはP-06に従い新規ADRまたは既存ADRのsupersedeが要る）
- どちらを選ぶにせよ、`test_structure.py`に`SECURE_REFERRER_POLICY`の期待値を検査する1行を足せば、
  今後の無断逸脱を機械的に防げる

このズレも実データ運用開始の妨げにはならないと判断する（非公開検索基点の露出という強い禁止事項には
抵触しない）が、「実データ運用に進む前に直すべきもの」の候補として明記する。

---

## 3. Hot Pepperフィールド名の仮定（既知事項の再確認）

`src/dining_radar/integrations/hotpepper/normalize.py`のdocstringは、この仮定が合成fixtureでしか
検証されていないこと、ADR-0002決定7により本リポジトリからのlive credentialed callが禁止されている
ことを自ら明記している。これは新規の発見ではなく、activeContext「Next work」#1・product-brief §8・
design.md「後続スライスへの条件」がいずれも既に開示している既知の限界であり、architectとして
再確認した上で以下を付け加える。

- `_normalize_shop`の欠損値処理は`_text_or_none`/`_int_or_none`という寛容な変換であり、
  想定したフィールド名（`catch`・`open`・`close`・`capacity`・`access`・amenity 5項目）が
  実際のAPI応答と食い違っていても、**例外は飛ばず該当項目が黙って`None`（画面上「情報なし」）
  になるだけ**である。一方、`name`・`genre.name`・`urls.pc`・`lat`・`lng`はコード上
  `HotPepperResponseError`で明示的に落ちる（62〜85行目のraise）。したがって「実キーを入れて
  動かしてエラーが出ない」ことは、必須5項目のフィールド名が合っている証拠にはなるが、
  **紹介文・営業時間・定休日・総席数・アクセス・設備情報のフィールド名が合っている証拠には
  ならない**——これらは黙って劣化するだけで、動作確認だけでは気づけない
- 推奨: 実キー・実座標を設定して動かす際、最初の1回は（1）公式ドキュメントの現行フィールド名を
  読んで`normalize.py`と突き合わせる、または（2）取得した生レスポンス1件をコミットしない形で
  目視し、`catch`/`open`/`close`/`capacity`/`private_room`等のキーが実際に存在し値が入っているかを
  確認すること。これは新しい要求ではなく、activeContext「Next work」#1が既に求めていることの
  実務上のやり方を具体化しただけである

---

## 4. ADRどうしの整合性

13本を通読した結果、相互矛盾は見つからなかった。要点のみ記す。

- **supersede関係は正しい**: ADR-0004（status: superseded, superseded_by: 0005）→ ADR-0005が
  正しく引き継いでいる。ADR-0004の帰結節の記述が現在のシステムを表さないことも、
  `product-brief.md`・ADR-0008「既存決定との関係」節が明示的に手当てしている（P-06準拠）
- **ADR-0011とADR-0013は同型の先例関係**として一貫している——両方とも「承認済み画面が
  test infrastructure層の契約を駆動してよい」という同じ機構を、ADR-0013が一般方針として
  明文化した。ADR-0013決定3が自らこの関係を正確に記述しており、矛盾はない
- **ADR-0012とmeta/adr/0021の関係**も整合している——「受理後の反復の担い手をdeveloperに早める」
  という判断は、meta/adr/0021決定2の骨格保持ルールの範囲内での適用であり、新しいメタ規律を
  必要としない（ADR-0012決定2の論証を追った限り妥当）
- **ADR-0002/0001の「利用履歴・ブラックリスト」記述とADR-0008の「保存しない」方針**は、
  ADR-0008「既存決定との関係」節が明示的に「過去の設計時点の記録であり導入を要求しない」と
  述べており、矛盾ではなく意図的な歴史の保存（P-06）である
- **ADR-0009とADR-0007の執行モデル分離**（TDR-CSはJS実行ブラウザ、TDR-AUTHはプレーンHTTP）は
  ADR-0013決定7が`renderModel`を追加した際に再確認・強化されており、一貫している

一点、軽微な観察として記録する: ADR-0008末尾「承認状態」節の文言（「現在の candidate-search PR が
マージされた時点で durable decision となる」）は、そのPR（#76）が既に何スライスも前にマージ済みである
現在の視点からは**歴史的スナップショットとして読めば正しいが、額面通り読むと未マージのように誤読され
うる**。ADRは編集禁止（P-06）であるため、これは修正提案ではなく単なる観察に留める——frontmatterの
`approved_by`が既に確定した承認を正しく記録しているため、実害はない。

---

## 5. product-brief / design.md / ARCHITECTURE.md と実体の整合

- **design.md**: 処理の流れ、非公開データの扱い、provider境界の記述は実装と一致している。
  「後続スライスへの条件」節の3項目のうち、credit文言確定・HTTPS確認は実装済み、フィールド名の
  実データ再確認は前述のとおり未了（既知）
- **ARCHITECTURE.md**: モジュール境界表（`authentication`/`web`/`suggestions`/`recommendation`/
  `integrations/hotpepper`）は`src/dining_radar`の実際のパッケージ構成と一致する。`records`
  モジュールは存在しないが、これはADR-0008が意図的に導入を見送った結果であり、ARCHITECTURE.mdの
  モジュール表にも`records`は載っていない——一致している。検証境界節の記述（L1〜L4の担当）も
  実際のCI構成（`ci-toyama-dining-radar.yml`）と一致する。唯一の逸脱が上記2節の`Referrer-Policy`
- **product-brief.md**: 受け入れの目安（コンセプト起点の比較、再提案での切り口変更、非公開情報の
  非露出）はTDR-CS/TDR-AUTHシナリオと実装によって満たされている

---

## 6. スコープの欠落（契約に無いが製品として要りそうなもの）

監査の過程で見た範囲では、致命的な欠落は無い。軽微な観察を2点のみ記す。

- **`authentication-acceptance-review.md`が`projects/toyama-dining-radar/`直下に置かれている**
  （`reviews/`配下ではない）。内容は既に解消済みのTDR-AUTH監査の記録であり、先例
  （`reviews/audit-tdr-cs.md`）に倣うなら`reviews/`配下にあるべきファイルである。実害はないが、
  将来の読み手が`reviews/`だけを見て監査履歴を把握しようとすると見落とす。移動または削除を推奨する
  （どちらもarchitectの権限内の軽微な整理だが、監査対象を書き換えない原則に従い、ここでは
  発見の報告に留め、移動自体はorchestratorまたは次のPRに委ねる）
- **ADR-0003が記述する受け皿スタック（React, TypeScript, Tailwind, shadcn/ui）と実際の
  `design-preview/package.json`の依存（react, react-dom, lucide-react のみ）が食い違っている**
  ことは、activeContext「Next work」#3で既に認識済みの宿題であり、今回`package.json`を読んで
  再確認した。出荷コードへの影響はゼロ（`design-preview`から出荷コードへの参照は無い、grep確認済み）
  であり、実データ運用のブロッカーではない

---

## 7. 検証の申告（meta/adr/0039）

- **機械実行したもの**: なし。architectはBash/pytest/npm実行手段を持たない
- **読んで突き合わせたもの**: `contracts/**`全7ファイル、`adr/0001`〜`0013`全13本、
  `product-brief.md`・`design.md`・`ARCHITECTURE.md`・`friction-log.md`、
  `src/dining_radar/**`の主要モジュール（`web/views.py`・`web/serializers.py`・
  `web/static/.../candidate.js`・`web/templates/web/home.html`・
  `integrations/hotpepper/{client,config,normalize}.py`・`recommendation/pipeline.py`・
  `urls.py`・`settings*.py`）、`tests/**`の構造検証・境界検証・受け入れテストDSL主要部
  （`test_structure.py`・`test_static_assets.py`・`test_test_support.py`・
  `test_authentication.py`冒頭・`tests/acceptance/dsl/candidate_search_browser.py`全文）、
  `env.example`・`pyproject.toml`・`.github/workflows/ci-toyama-dining-radar.yml`、
  `reviews/audit-tdr-cs.md`、`design/reconciliation/candidate-card-refinement.md`、
  `design-preview/package.json`
- **読んでいないもの**: `tests/acceptance/dsl/js_browser_mechanics.py`・`openapi_schema.py`・
  `browser_mechanics.py`の全文（reviewerが既に監査済みのため`audit-tdr-cs.md`の記載を信頼した）、
  `authentication/forms.py`・`throttle.py`の全文、`suggestions/**`の全文、`tests/`のその他の
  L1単体テスト本文（構造・件数の主張はorchestrator/reviewerの申告を信頼し独立再検証していない）
- **1節・2節の指摘は文字列の突き合わせによる発見であり、実行して再現したものではない**——
  `ALLOWED_CONTROL_PURPOSES`の値の不一致と`FORM_CONTROL_SELECTOR`のセレクタ一覧は
  ソースコードを読んだ上での静的な論理的帰結であり、Playwrightを実際に動かして
  「このコントロールが検査されないこと」を再現したわけではない。人間またはtester/reviewerが
  実行して確認することを推奨する

---

## 8. 結論

- [x] **実データ運用（ローカル・非公開環境での実キー・実座標稼働）に進んでよい**
- [ ] 契約側の欠陥により差し戻し
- [ ] 実装側の欠陥により差し戻し

**条件**:
1. 実キー投入直後、必須5項目（`name`/`genre`/`urls.pc`/`lat`/`lng`）以外の任意項目
   （紹介文・営業時間・定休日・総席数・アクセス・設備情報）が実際に値を持つかを目視確認すること
   （3節）。エラーが出ないことだけでは正しさの証拠にならない
2. `Referrer-Policy`の実装値とADR-0008/ARCHITECTURE.mdの決定文の食い違いは、実データ運用の
   ブロッカーではないが、次に触れる機会に解消すること（2節。案A/Bいずれか）
3. `auth-account-menu-toggle`のL4検証ギャップ（1.2節）は、次にcontrol surfaceに触れるスライスで
   tester/reviewerが解消すること。現時点でセキュリティ・プライバシー境界への実害はない
4. 「実データ運用」は、デプロイスライス（ADR-0042）が未着手である以上、**当面ローカル・非公開環境に
   限られる**。インターネット公開には別途TDR-AUTH-06の実HTTPS検証（ADR-0007が定義済みだが未実施）
   が要る

いずれの条件も、実データ・実座標を設定してローカルで動作確認を始めること自体を妨げるものではない。
