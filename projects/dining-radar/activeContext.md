# activeContext.md — Dining Radar

> P-11: このファイルは**現在だけ**を映す。歴史は git と ADR が持つ。
>
> **2026-09-11、全面圧縮した。** このファイルは 2026-08-24 以降ラウンドごとの実装ログを追記し続け、
> 2,315行・276KB まで肥大して P-11 に違反していた（agent が起動時に安全に読めない大きさであると
> architect が指摘）。圧縮前の全文は `094f323` の
> `projects/dining-radar/activeContext.md` にある。消したのは「いつ誰が何を実装したか」の叙述で
> あり、決定は ADR に、成果物は git に、摩擦は `friction-log.md` にそれぞれ残っている。
> **追記運用へ戻さないこと。**ラウンドの記録を残したくなったら、それは ADR か friction-log の仕事。

## この製品の現在地

`dining-radar` は、**幹事が昼の会を立て、参加者が日程と店を答え、幹事が決める**ところまでを扱う
Web アプリである。公開運用中（Render + Neon、カスタムドメイン。URL はリポジトリに書かれていない
——`adr/0021` の 2026-08-14 追記。実データでの見え方を確かめたいときは人間に開いてもらう）。
`main` へのマージは CI 通過後に Render が自動デプロイする（`render.yaml` の
`autoDeployTrigger: checksPass`）。

プロジェクト名は 2026-08-20 に `toyama-dining-radar` から改名した（`adr/0026`）。公開リポジトリに
実在の県名を持ち込まないため（`product-brief.md` §4・`adr/0002`）。Python パッケージは元から
`dining_radar` で、import・settings・static パス・CSS クラスは動いていない。シナリオ ID の接頭辞
`TDR` もそのまま（承認済み契約を含め 738 箇所に出現するため）。**改名しても公開リポジトリから地域が
消えたわけではない**——`toyama-weekend-radar` と `connpass-session-radar` は今も持っている。

機能の骨格:

- **店を絞る画面**（TDR-CS）: 認証済みの幹事が、徒歩圏・ジャンル・予算・設備で候補を絞り、地図と
  カードで比べる。PC は2カラム（`renderModes.twoColumnLayout`）、スマホは地図主体。
- **会の画面群**（TDR-GTH）: 会の作成、候補日の一括登録（カレンダー複数選択）、参加者への署名付き
  共有リンク配布、日程の3段階回答、店の3段階投票、開催日と店の確定、会の削除。
- **店選びは候補検索画面へ一本化した**（`adr/0049` 決定1）。会モード（`/?gatheringId=<id>`）で
  候補検索画面を開き、カードのトグルで会に入れる/外す。会側に別の店選択画面は**もう無い**。

`product-brief.md` は 2026-08-30（PR #174）で改訂され、会・日程調整・出欠・承認投票を製品境界の
**内側**に入れた。**履歴（過去に行った店の記録）だけは今も境界の外**（§7）——再検討には人の決定と
ADR が要る。

## いま進行中のスライス（2026-09-11）

**実機フィードバック大改訂**（人間が公開環境で使って出した12件＋追加3件）。ブランチ
`integrate/gathering-field-feedback`。

取り込んだ人間裁定と、それを載せた ADR:

| ADR | 内容 |
|---|---|
| `adr/0049` | 店選びを候補検索画面へ一本化／候補日はカレンダー複数選択／PC 2カラム化（送りボタン・件数カウンタ廃止）／日程回答時は開いている店の**件数だけ**出す |
| `adr/0050` | **可視性の反転**（自分が答える前から他人の回答が見える）／確定後の記録を1行へ簡素化／**会の削除を置く**（旧 D4 の「削除操作は置かない」を覆した） |
| `adr/0051` | 会をつくる画面の候補日入力も同じカレンダーへ統一 |
| `adr/0052` | `GATHERING_OPEN_SHOP_WEEKDAY_MATCH` の shopId 安定性と表示上限を文書化（Given 構築が曜日と表示上限に偶発的に依存していた3件の破綻を決定的な技法へ作り直した） |
| `adr/0053` | TDR-GTH-26〜41 を店選択画面の撤去に対して1本ずつ棚卸し（結論: 16本すべて現状のまま成立） |

ブランチの現在の状態:

- `integrate/gathering-field-feedback` に実装・テスト・契約の全ブランチを合流済み。
  `contracts/gathering-field-feedback`（`adr/0052`・`0053`、`test-support-api.yaml` v1.5.7）も
  取り込んだので、**契約文面とコードの食い違いは解消している**（reviewer が「マージ順序の懸念」
  として挙げた件）。
- orchestrator が自分で再実行した検証（role の自己申告は採らない）:
  L4 受け入れ 76件 OK（916s）／L5 `tests/ui_invariants` 14件＋10 subtests 緑／`ruff check .` 緑／
  `govlint` エラーなし。
- reviewer の独立監査は `reviews/audit-gathering-field-feedback-steps.md`。**Blocker 0**（検査内容に
  対して）・Major 2・Minor 3。**Major 1・2 と Minor 1・3 は是正済み**（`569a231`）:
  - **Major 1**（TDR-CS-18 の絞り込みが実質非検証）: Given を件数の分からない汎用母集団から
    `GATHERING_OPEN_SHOP_WEEKDAY_MATCH` へ差し替え、**月曜**（既知の開店数5件）に固定して、
    `search_again` を収束するまで回し、出現した distinct shopId がちょうど5件であることを数え上げる。
    **月曜を選んだのが要点**——開店数5件が表示上限5件とちょうど一致するので、1回の応答だけでは
    「絞り込み無し（実際は6件）」と「正しい絞り込み（5件）」を区別できない。だから収束まで回す。
  - **Major 2・Minor 1**: `GET /gatherings/{id}` を直接叩き `shortlistedShops[].shopId` を読んで、
    検索し直しの前後で5件の**集合が完全一致**すること（同一性の保存）と、帯の件数がサーバー実値と
    一致することを検査する。
  - **Minor 3**: answerLater/peekResults の機能化テストの末尾で FR-030 横断検査を1回呼ぶ。
  - 4件とも**欠陥注入で赤くなることを実証済み**（ADR-0065 に従いコミットには残していない）。
  - Minor 2（構造的に同一の画面のデータ違いバリエーションで FR-030 を再実行していない）は監査自身が
    「実害リスクは低い」と判定しており、**次にこの画面群を触るラウンドへ送る**。
- **TDR-GTH-48 の間欠失敗（`net::ERR_ABORTED`）の真因を特定して直した**（`b8a70db`）。削除が 204 を
  返すと画面自身が `window.location.href` で遷移するのに、テスト側がその進行中の遷移に重ねて自分でも
  `page.goto` を出していた。**契約は削除直後の遷移先を固定していない**（`deleteGathering.confirm.
  requiredOutcome` は「その後この会が一覧に出ないこと」だけを要求する）ので、遷移先を要求せず
  `expect_navigation()` をクリック**前**に登録して「何であれ起きた遷移が終わるまで」待つ形にした。
  試して駄目だった案が2つあり、docstring に理由まで残してある（DELETE 応答の body を読む案は、
  画面側の遷移がリソースを回収してしまうため**毎回確実に**失敗する。応答イベントだけ待って
  `wait_for_load_state` を呼ぶ案は、まだ遷移が始まっていない時点では即座に返るため空振りする）。
  **修正前に20回回して 2/20 の失敗を再現し、修正後は10/10 緑**。

契約は `gathering-scheduling.feature`（TDR-GTH-01〜48）・`candidate-search.feature`
（TDR-CS-00〜19、07 は廃止）・両 `-api.yaml`・両 `-browser-interface.yaml`。**いずれも
2026-09-11 のチャットの合意として承認済み**（`meta/adr/0064` 決定1: 合意はチャットで取り、
PR のマージは決まったことを公表する操作にする）。`adr/0052`・`0053` も同じ裁定で `承認済み` にした
——**承認だけの追いPRを後から出す繰り返し**（リポジトリ全体で7回、FR-008/016/017）を
ここで作らないための運用である。

## 確定ポリシー

- 実在の生活圏名・座標・設定した範囲・API キー・秘密・provider のリクエスト URL / レスポンス・
  店 ID・画像・店データ・実データ移行・fixture・DB ダンプを**コミットしない**。合成データのみ使う。
- provider のレスポンスを**キャッシュ・永続化しない**。恒久的な provider ID や HMAC 由来の照合
  データも使わない。これを開け直すには新しい人間の決定・provider 規約の再確認・ADR が要る
  （`adr/0018` は両方を検討したうえで `提案中` のまま）。
- API キーはサーバから provider へだけ送る。キーを含む URL・provider の内部・私的な基点を、
  ブラウザ・公開 URL・ログ・エラー・トレースへ出さない。
- 地図は Leaflet + OpenStreetMap 標準タイルのみ、認証済みの小規模な対話利用に限る。帰属表示を出し、
  タイルの先読み・一括取得・オフラインキャッシュをしない。地図が私的な基点を露出してはならない。
- Leaflet 自体（JS・CSS・マーカー画像）と flatpickr（4.6.13、MIT）は `static/` 配下に vendoring し
  同一オリジンで配る（`adr/0010` と同じ規約）。認証済み画面は third-party script を1本も読まない。
- 候補検索の endpoint は認証済みの幹事に依存する（`adr/0006`）。参加者は署名付き共有リンク
  （ログインなし・名前自己申告・使い捨てトークン）で入る（`adr/0034`）。
- 認証済み候補画面のコントロールは、TDR-AUTH の素の HTTP DSL が観測する範囲では、クライアント JS が
  差し込むのではなく**サーバがレンダリングした HTML に出ていなければならない**
  （`authentication-browser-interface.yaml` v0.2 `renderModel`）。
- **provider データが裏づけないことを主張しない。**居酒屋・バー系ジャンルの除外は「昼にやっている
  か分からない」という不確かさの記録であって、やっていないことの主張ではない。カード払いの注意書きも
  現金のみとは決して言わない。
- 会は店の情報を持たない。**保存するのは店 ID だけで、表示のたびに provider から取り直す**
  （`adr/0034` 決定6、live projection）。
- ブラウザに持たせた provider 由来の値には 24時間以下の上限を必ず付ける（provider 規約。下記）。
  `shownCandidateMemory` は 20時間、読むたびに刈る、タブの外へ出ない。

`manage.py` は `projects/dining-radar/.env.local` があれば読む（stdlib のみ・`os.environ.setdefault`
なので実プロセスの環境が必ず勝ち、ファイルが無ければ何もしない）。これは開発者の便宜専用で、
デプロイは `wsgi.py` を通り、このパスに一切依存しない。

## provider の実測値（2026-08-10、人間自身のキーと私的な基点）

設定された基点に `lunch=1`・`count=100`・設定範囲で直接叩いた結果と、provider の予算マスタ。
仮定ではなく実測である。

- `results_available` = 64、`results_returned` = 64。**母集団全部が1リクエストに収まり、切り捨ては
  起きていない。**`range` を最大にすると lunch フィルタ付きで 94、それでも 100 の上限未満。
- `card`: 48 可 / 16 不可（64件すべて埋まっている）。`non_smoking`: 全面禁煙 37・一部禁煙 14・
  禁煙なし 13（同上）。
- `budget.name` は 64/64 埋まっている。`budget.average` は 59/64 で自由文が混ざる
  （`通常平均：3000円 / 宴会平均：3500円`）ため、`normalize.py` は `name` を読む。
- ジャンル分布: 居酒屋 24・和食 9・カフェ・スイーツ 7・創作 7・ラーメン 4・イタリアン/フレンチ 4・
  洋食 3・焼肉/ホルモン 2・ダイニングバー/バル 2・その他 2。既定のジャンル除外後は 38。
- provider 側 `non_smoking=1` は 51（＝全面＋一部）、`card=1` は 48（＝ローカル集計と一致）。
  現在の母集団規模では provider 側フィルタとローカルフィルタは完全に一致する。
- 予算マスタは **17コード**（B009 〜500円 〜 B014 30001円〜）あり、`budget` パラメータは**最大2個**
  しか受け取らない。**3段階の粗い区分は provider 側では表現できない**（低位に4コード、高位に11コード
  要る）。だからローカルで絞る。

## デプロイ先の規約と実測（2026-08-12 確認、2026-08-14 訂正）

- **Render 無料 web**: health check は**エッジを通さずサービスのポートへ直接届く**ので
  `X-Forwarded-Proto` を持たない。`Host` はサービスの `onrender.com` サブドメイン（または検証済み
  カスタムドメイン）。**5秒以内の 2xx か 3xx** で成功扱い。15分無通信でスピンダウンし、起床に約1分。
  月 750 インスタンス時間。ファイルシステムは揮発、SSH 無し。
- **Neon 無料**: プロジェクトあたり 100 CU時間・0.5GB、5分で scale-to-zero、10ブランチ、
  6時間の instant-restore。無期限（試用ではない）。Render 自前の無料 Postgres は作成30日で失効する
  ため採らなかった。
- **Hot Pepper**: 必須のテキスト表記は
  `Powered by <a href="http://webservice.recruit.co.jp/">ホットペッパーグルメ Webサービス</a>` で、
  API を使う全ページに出す。`serializers.PROVIDER_CREDIT` がこの文字列と完全一致し、`candidate.js`
  が描くので満たしている。飲食店から金を取るサイトでの利用は禁止（アフィリエイト収益は可）。
- **キャッシュ条項は存在する。**利用規約に
  `個別に定める規定がない場合はキャッシュの更新頻度を24時間以内と定めます` がある。取得情報を
  第三者のデータベースへ複製することも禁じている（このオリジンの `sessionStorage` はそれに当たらない）。

  > 2026-08-12 の記載は「provider はキャッシュ規則を定めていない」と書いていた。**これは誤り**で、
  > API リファレンスとご利用案内だけを読み、利用規約本体（`regulation.html`）も、**この件について
  > このプロジェクト自身が持っていた `adr/0018`（24時間という数字を 2026-08-09 から逐語で引用して
  > いた）も読まずに**否定を記録していた。教訓は「もっと web を読め」ではない。**外部規則が存在
  > しないと断言する前に、リポジトリ自身のその規則の記録を先に読め。**

**本番設定モジュールに対するローカル実測**（`RENDER` あり・`DJANGO_DEBUG` なし・Neon の代わりに
使い捨て SQLite）: `collectstatic` は 136 ファイルをコピーし 398 を後処理、manifest の欠落なし。
`X-Forwarded-Proto` 経由で `request.is_secure()` が真。ブラウザ相当の `Origin`/`Referer` を付けた
CSRF 有効なログイン POST が 302 を返すので、**Render のプロキシ配下では `CSRF_TRUSTED_ORIGINS` の
登録は要らない**。`sessionid` は Secure+HttpOnly+SameSite=Lax、`csrftoken` は Secure+SameSite=Lax。
`check --deploy` は `security.W005`・`W021`（HSTS の subdomains と preload、意図的に off）を出す。

本番ビルドはこれに加えて **`security.W009`** を出す。ローカルの検査では予測できなかった——検査側が
50文字の秘密を自前で与えていたのに対し、Render の `generateValue: true` は 256bit 乱数を base64 で
**44文字**にして渡すため、Django の `len < 50` の腕だけが引っかかる。長さヒューリスティックが密度を
読み違えているだけであり、これを回避しようとすると人間が署名鍵を見て貼る経路ができて却って悪い。
**そのままにしてある。**

**この方法で見つけて直した実害の欠陥**: `RENDER` あり・`X-Forwarded-Proto` なしの `GET /healthz` が
**301** を返していた（`SECURE_SSL_REDIRECT` が on で `SECURE_REDIRECT_EXEMPT` が空だった）。
Render はポートへ直接投げ 3xx を成功と見なすので、**readiness probe は `SELECT 1` を一度も走らせない
まま健康と報告されていた**。`SECURE_REDIRECT_EXEMPT = [r"^healthz$"]` を入れた。再実測: 素の HTTP の
`/healthz` は 200 `ok`、`/`・ログインパス・`/healthz/`・`/healthzz`・`/x/healthz` はすべて 301
——**完全一致のみで、前方一致でも部分一致でもない。**

## 公開オリジンの L5（2026-08-14、外部から curl で実測）

- `/healthz` は 200 `ok`。スピンダウン明けの初回は 15.2s（Render の公称の起床時間と一致）。
- `http://…/` は 301 で HTTPS へ。未認証の `/` は `/accounts/login/?next=/` へ 302。
- ログインページは 200 で、**`href` が1つも無い**——公開サインアップもメール再設定の導線も無い
  （`TDR-AUTH-03` の要求）。
- 実レスポンスのセキュリティヘッダ: `strict-transport-security: max-age=31536000`
  （includeSubDomains なし・preload なし、設計どおり）、`x-content-type-options: nosniff`、
  `x-frame-options: DENY`、`referrer-policy: strict-origin-when-cross-origin`、
  `cross-origin-opener-policy: same-origin`。
- 配信 HTML にもヘッダにも、API キー・座標・provider URL・範囲は出ていない。404 は 179バイトで
  フレームワーク名もトレースバックも設定も名指ししない。
- 認証済み画面は人間が確認（orchestrator は資格情報を持たない）: カードと地図が出る。必須の表記
  2件（`Powered by ホットペッパーグルメ Webサービス` と `© OpenStreetMap contributors`）とも出る。
  外部通信は OSM のタイル取得のみ——これは意図した境界である（`adr/0010` が Leaflet 自体を同一
  オリジンに vendoring し、タイルだけは必然的に OSM から取る。`product-brief.md` §3 が地図の表示
  範囲が provider に届くことを既に受け入れている）。`Referrer-Policy` がその開示をオリジンだけに
  抑える。**タイル URL の `z/x/y` は位置の開示そのものなので、issue・PR・コミットメッセージに
  貼らないこと。**
- **`/healthz` の除外は本番で効いていることを、推測ではなく実測した。**gunicorn のアクセスログを
  一時的に有効にすると `"GET /healthz HTTP/1.1" 200 2` が RFC1918 の私的アドレスから user agent
  `Render/1.0` で数秒おきに届いていた。200 は `SECURE_SSL_REDIRECT` を否定し、2バイトの body は
  `ok` なので view 自身が `SELECT 1` を走らせて答えており、私的な送信元はエッジを迂回していること
  の一次証拠になる。

  > ここへ至る過程で**検証手順自身の欠陥**が出た。2026-08-12 に `DEPLOYMENT.md` へ書いた
  > 「素の HTTP の `/healthz` が 200 を返すこと」は**公開インターネットからは実行不能**である
  > （Render のエッジが gunicorn より手前で 301 を返す）。代わりに Neon の compute を見る案を出したが、
  > 人間が試して「何も決まらない」と言った。**人間が正しい**——グラフの時間分解能が粗く、利用者の
  > トラフィック・検証のトラフィック・health check が同じ線に乗るので、5分と15分の閾値を区別できない。
  > `DEPLOYMENT.md` §3-3 はアクセスログ方式を規定し、Neon 方式を明示的に禁じている。**何も検証して
  > いないのに緑に見える検査は、検査が無いより悪い**——これは検証手順そのものにも当てはまる。

## 検証の層（いま動いているもの）

`meta/verification.md` の L0〜L5 を CI（`ci-dining-radar.yml`）が全部回す。

- **L0** govlint（統治文書の整合）＋ ADR 採番の衝突検査
- **L1** 単体・ruff・カバレッジ・mutation（pytest-gremlins。対象は `src/dining_radar/**.py` のみ）
- **L2** 構造境界 / **L3** 認証・provider・設定の境界（`manage.py check` ×2プロファイル）
- **L4** 受け入れ（Playwright。`tests/acceptance`。TDR-AUTH・TDR-CS・TDR-GTH）
- **L5** `tests/ui_invariants`（`adr/0020`）。`l4-acceptance` に `needs` で続く独立ジョブ。
  DOM/幾何の不変量4件（狭い幅での地図到達性・キーボード到達と起動・内部 enum の非露出・
  コントロール44px 下限）を実画面に対して測る。DSL は Given 構築と遷移にだけ再利用し、assert には
  使わない。

この層が実際に欠陥を捕まえた例（関所が飾りでないことの証拠として残す）: 地図マーカーは Tab で
到達できるのに Enter/Space で選べなかった（Leaflet は popup を持つマーカーにしか keypress を click へ
翻訳しない。vendoring した `leaflet.js` を読んで確認）。`candidate.js` に明示の keydown を足した。
修正を戻すと当該テストだけが赤くなることまで確認している。

**L5 の 44px 検査で踏んだ CI 固有の罠（FR-013）**: 閉じた `<details>` の中のコントロールに対する
`bounding_box()` は未規定で、同じ Chromium でも Windows では実サイズ、Ubuntu では一貫してゼロを
返した。`is_visible()` は両方で決定的に `False` を返すので、**いま開示されているコントロールだけを
測り、各フェーズで測定件数が非ゼロであることを assert する**形にした（アカウントメニューのコントロールは
除外ではなく、メニューを開くフェーズへ**先送り**）。閾値は下げていないし assert も外していない。

**既知の検証ツールの欠陥（未修正）**: `tools/check_mutation_score.py` は
`coverage/gremlins/gremlins.json` の鮮度を確かめずに読むので、mutation の実行が失敗すると前回の
スコアが残ったまま**緑を報告する**。この Windows 機では `pytest --gremlins` がそもそも走らない
（テストが増えて子プロセスのコマンドライン長が上限を超える。`WinError 206`）。CI は Ubuntu で、
失敗した pytest の時点で止まるので影響を受けない——**露出しているのはローカル実行の経路だけで、
そこはまさに「ローカルで検証した」と主張する経路である。**修正は developer の仕事（orchestrator の
仕事を採点する道具だから）。`meta/tools/**` は `meta/adr/0046` でロックされており人間の解錠が要る。

## ローカルで画面を確かめる手順

```
python manage.py runserver 127.0.0.1:8741 --settings=dining_radar.settings_localdemo --noreload --insecure
```

- `settings_localdemo.py` と `localdemo.sqlite3` は**リポジトリに入れない**（`.gitignore` 済み、
  FR-027）。無ければ `settings_acceptance` を継承して sqlite のパスと `ALLOWED_HOSTS` を差し替える
  だけの数行で作れる。
- **サーバ起動のたびにデータの再投入が要る**（モードは LocMem キャッシュ保持のため再起動で消える）:

  ```
  curl -X PUT http://127.0.0.1:8741/test-support/candidate-proposals/state -H "Content-Type: application/json" -d "{\"mode\":\"NORMAL_WITH_WEIGHTED_SAMPLING\",\"randomSeed\":7}"
  ```

- **`home.html` を変えたらサーバの再起動が要る**（`DEBUG=False` で Django がテンプレートをキャッシュ
  する）。これを忘れて「直っていない」と誤報告した事故がある（FR-025）。
- **合成候補は経度0固定で南北一直線に並び、現在地は海の上**である。ピンが縦一列なのはデータの性質で
  あって不具合ではない。**実データの2次元の散らばりでの見え方は、この環境では確かめられない。**

## Next work

1. **実機フィードバック大改訂を着地させる**（進行中。上記「いま進行中のスライス」）。
   監査の是正と TDR-GTH-48 の競合修正は取り込み済み。orchestrator による全層の再検証と PR が残り。
2. **Hot Pepper の生 JSON のフィールド名**を、現行の公式ドキュメントに対して再確認する
   （provider 表記・無料プラン・health check の規約は 2026-08-12 に再確認済みで上記に記録済み）。
3. **`project/toyama-dining-radar` ブランチの処遇を決める。**ブランチ名と ruleset は旧名のまま
   （2026-08-20 の改名が意図的に触らなかった）。`main` はこのブランチより大きく先行し 0 behind なので、
   このブランチは遅れるだけである。fast-forward するか、`main` から直接スライスを切る（最近のスライスが
   実際にやっていること）方へ寄せて捨てるかを決める。
4. **`design-preview` の残骸を人間が消す**（`adr/0028` 決定2）:
   `projects/dining-radar/design-preview/` と `.claude/launch.json` の
   `dining-radar-design-preview` エントリ。
5. **govlint の `SCENARIO_ID` パターンが `TDR-CS-01`・`TDR-AUTH-01` にマッチしない**ので、
   TDR 系のシナリオ ID は L0 で一度も検査されていない。修正には `meta/tools/**` の人間による解錠
   コミットが要る（`meta/adr/0046`）。
6. **`candidate.js` のクライアント側 JS 単体検証層**（`adr/0014`）は未実装。ADR 自身が「この層で
   見つかったはずの欠陥は、これまでのところ1件も無い」と明記している——価値は将来の回帰捕捉であって、
   過去の埋め合わせではない。
7. **余白とボタンの小ささの是正**は、カレンダーと削除ダイアログの新規 CSS で部分的に対応したのみ。
   既存画面全体を designer のボードに対して px 単位で突き合わせる作業は**していない**。
8. **スマホでカードが1枚ずつきっちり止まるか**は未計測。人間の実機報告（スワイプでカードが見切れる）は
   再現しなかった。`candidate.js` の `deckSwipeState` には既に手の込んだ実装がある。

## Open questions

- メール配信と SSO は先送りのまま。アカウントは招待制・ローカルのまま。カスタムドメインの件は決着済み
  （Route 53 のサブドメイン。`adr/0021` の 2026-08-14 追記）。
- 「承認済み画面がテスト基盤のコントロール面契約を駆動する」型（`adr/0011`・`adr/0013`）を
  `meta/adr/0023` の隣に meta ADR として一般化すべきか。architect が提起した。meta ADR の起草は
  orchestrator の領分（`meta/adr/0047`）。
- `adr/0020` のハーネスを meta 層へ一般化すべきか。ADR 決定10 は意図的にこのプロジェクトに閉じ、
  判断を orchestrator へ預けている。最初の証拠は出た（導入したスライスで実際にキーボード起動の欠陥を
  捕まえた）。一般化するなら、Playwright/TypeScript の `reservation-frontend` へ同じ不変量をどう届けるか
  と、`meta/tools/**` のロック解錠（`meta/adr/0046`）に答える必要がある。
- **輪とラベルの対応（F1b、Medium、2026-08-27 reviewer）**: 徒歩圏の輪の分数ラベルの検査は
  「可視ラベルの分数の集合」と「輪の `data-walking-radius-minutes` の集合」が一致することまでしか
  証明していない。**集合が保たれたまま対応だけが入れ替わる欠陥**（5分の輪に「15分」と出る）は
  検出できない。恒久的に閉じるには実装と契約の両方が要る（ラベル要素に輪と相関する属性を持たせ、
  それを契約の Must に載せる）。architect の判断が要る。可視ラベル要素に `data-testid` が無く DSL が
  CSS クラスを手がかりにしている件（`by_test_id` 規約からの逸脱）も、**同じ1件として扱ってよい**。
- **ラベルの遮蔽は機械的に証明できない**（2026-08-27）。人間の実機報告「15分の表記が店の位置により
  隠れて見えない」に直接対応する性質だが、Playwright の可視判定は遮蔽をモデル化しない。現状は
  実装側の衝突回避配置に依存しており、関所は無い。
- **輪のラベル・ピンがカードに隠れないことは合成データでしか測っていない**（経度0固定・南北一直線）。
  実データの2次元の散らばりでの見え方はこの環境では測れない。
- **デッキ送りの `pendingFilters` 不変検査が PC のボタン側だけ未実装**（2026-08-29 reviewer）。
  契約（`browserActions.pageDeckPrevious`/`pageDeckNext` の `unaffected`）は既に両方を要求しており、
  欠けているのはテスト側のコードだけ。**注意: `adr/0049` 決定4 で PC は2カラム化され送りボタン自体が
  廃止されたので、この項目が今も成立するかは次に触る人が確かめること。**
- **監査 Minor 2**（2026-09-11 reviewer）: FR-030 横断検査が、構造的に同一の画面のデータ違い
  バリエーション（TDR-GTH-12/29 の tally 可視状態、TDR-CS-18 の絞り込み状態、TDR-CS-19 の 5件到達
  状態）で再実行されていない。監査自身が実害リスクは低いと判定。次にこの画面群を触るラウンドで拾う。
- **未説明の L4 間欠失敗が1件ある。**developer の仮説（実行中の同時ファイル編集）は確認されていない。
  2026-09-06 に真因を特定して直した3件（Django が in-memory SQLite で LiveServerTestCase の複数
  スレッドに1本の接続を共有して savepoint が壊れる件ほか）と同じ種類かどうかも分からないまま。
  その後この事象は再発していない。
- **作業ツリー `E:/AWS/arc2` がマージ済みブランチ `docs/walking-time-detour`（PR #161）のまま
  残っている。**別セッションが使っている可能性があるため触っていない。放置すると `meta/adr/0062` が
  記録した「古いツリーのまま作業して役割定義が届かない」事故の再発条件になる。所有者を確かめて
  片付けること。
- **`TDR-CS-11` が `shownCandidateMemory` を直接消している。**reviewer は必要性は本物と判断したが、
  契約はこれを認可された seam として名指ししていない（有効期限の件とは違って）。意図的に解決せず
  抱えている。

## 承認の状態

`product-brief.md` は 2026-07-31 にチャットで人間承認、以後の改訂は PR のマージで durable になって
いる（no-history/no-durable-identifier の追補、夕食予算の改訂、フィルタ模型に伴う「決定的ルールのみ」
の緩和の明記、2026-08-30 の会スコープの取り込み）。個々の ADR・契約・実装がどの PR で durable に
なったかは、**ADR の frontmatter と git が持っている**——ここで PR 番号を並べ直さない（下記の慣行）。

2026-08-01 の人間裁定: `TDR-AUTH-01`〜`05`・`07` は L4 のブラウザ検証、`TDR-AUTH-06` は L3 検証、
HTTPS の transport 検証はデプロイまで先送り。

**機械的な関所が無い箇所として記録しておく。**`tests/acceptance/**` を変更した PR に対する reviewer の
独立監査（`meta/agents.md` §4 step 7）は、PR #88 と PR #156 の2回、実施されないままマージされた。
どちらも orchestrator が事前に申告し、人間がそのままマージした——`meta/adr/0035` 方式(i) では
**マージが承認行為**なので規程違反ではなく人間の判断である。ただし**監査を回すかどうかが毎回
orchestrator の申告と人間の裁量に委ねられており、PR テンプレのチェック欄は自己申告にすぎない。**

`record-update-needs-second-pr`（ADR の承認記録を閉じるのに追加の PR が要る）はリポジトリ全体で
7回起きている。FR-008 が5回目を「慣行より仕組みを選ぶ地点」と名指しし、FR-016・FR-017 が6・7回目。
FR-017 が提案した検査——本文で「この PR のマージで承認」と宣言している ADR の frontmatter が
`提案中` のままなら govlint を落とす——は、`meta/tools/**` が `meta/adr/0046` でロックされていて
人間の解錠コミットが要るため未実装のまま。

**このファイルの慣行（FR-008）**: 進行中の PR の承認状態をここに書かない。PR・ADR の frontmatter・
git が既にその事実を持っており、複製すればマージした瞬間にこのファイルが嘘になる（P-04）。
**存在するものを書き、承認の記録は承認行為が起きる場所に置く。**
