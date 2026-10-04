---
id: 0068
scope: project/dining-radar
status: 提案中
date: 2026-10-04
approved_by: null
supersedes: []
superseded_by: null
relates_to:
  [P-02, P-06, P-08, ADR-0036, ADR-0058, ADR-0061, ADR-0062, ADR-0063,
   ADR-0066, TDR-GTH-03, TDR-GTH-17, TDR-GTH-35, TDR-GTH-36, TDR-GTH-67]
---

# ADR-0068: 店を選び中の画面では「リンクを発行」を「リンク」タブの中だけに置き、店タブ・日程タブ・回答タブには出さない（板S4どおり）

> **承認者向けサマリ**: 板`party2/d7/S4-SpSelect.dc.html`・`S4-PcSelect.dc.html`（店を選び中）は、
> 店タブの見出し行を「票が多い順」と「店を絞りなおす」の2点だけで描いており、「リンクを発行」
> ボタンは板のどこにも無い（板にあるのはタブ「リンク N本」のラベルだけ）。ところが現在の契約
> （`gathering-scheduling-browser-interface.yaml` 0.25.0）の`participantLinkCopy.presenceRule`は
> 「SCHEDULINGまたはSELECTING_SHOPの間は常に存在」で、実装はそれに従って**4つのタブすべて**に
> このボタンを出している（店タブでは見出し行に「店を絞りなおす」と並べ、日程・回答タブと店0件の
> 画面では専用の1行を足している）。2026-10-04、人間は選択肢B「板どおり」を裁定した。
>
> 本ADRは1点を決定する。**店を選び中（SELECTING_SHOP）の間、`participantLinkCopy`
> （`gathering-participant-link-copy`）は「リンク」タブ（`shopSelectionPanel.linksTab`）が選ばれて
> いるときだけ見え、店・日程・回答の3タブでは見えない。**SCHEDULING局面（タブ群が無い、いまの
> 画面）と、FINALIZED局面（もともと不在）は変えない。契約は0.25.0から0.26.0へ上げる（ADR-0063
> が0.24.2から0.25.0へ上げたのと同じ、`presenceRule`の意味が変わる改訂は minor を刻む慣行）。
> **新しい業務シナリオは足さない**（置き場所はUIの構造であって業務規則ではない。ADR-0063が
> タブ構造に`.feature`を足さなかったのと同じ扱い）。検証は、既存のL5不変条件テストの書き換えと、
> L4のDSLの下準備の修正で受ける。
>
> **人間に確認してほしい点が1つある**（未決事項1）: 板S4は「リンク」タブの**中身**を描いていない。
> 「リンクを発行」をそのタブの見出し行（「発行済みリンク」の右）に置く、というのは architect が
> 既存の実装の姿（`gathering.js`の`links`分岐が既にそうしている）から起こした推定であり、板が
> 示した形ではない。この置き場所でよいかを、承認のときに見てほしい。

## 文脈

### 0. 検証の申告（meta/adr/0039）

次を実際に`Read`・`Grep`して確認した: `gathering-scheduling-browser-interface.yaml`
（contractVersion 0.25.0）の`organizerDashboard.participantLinkCopy`（`presenceRule`・
`requiredOutcome`・`issueDialog`）・`shopSelectionPanel`（4タブ、`linksTab.requiredOutcome`）・
`participantLinkList`・ヘッダの追補24、`gathering-scheduling.feature`のTDR-GTH-03/16〜20/35/36
の本文、ADR-0061決定1・ADR-0063決定3と検討した代替案、`gathering.js`の
`renderShopSelectTabContent`・`renderShopSelectionPanel`・`renderParticipantLinkPane`、
`organizer.css`の該当節、`tests/acceptance`（DSL・steps・テスト本体の呼び出し元）・
`tests/ui_invariants`（`test_render_invariants.py`・`test_layout_sanity.py`・
`test_zz_capture_states.py`）・`tests/test_gathering.py`、および板`d7/S4-PcSelect.dc.html`の
文言（`リンク 9本`・`票が多い順`・`絞りなおす`のみで、`発行`を含む文言が無いこと）。
`.orca/drops/`配下の他の板で「リンクを発行」を描くのはSCHEDULING局面の板（`a-nav-r5`・`b2`・
`c2`）だけで、SELECTING_SHOPの板（`d5`〜`d7`・`f1`の`N3`/`N4`）にはどれも無いことも
`Grep`で確認した。確認していないのは、実装の実機での見え方とCIの実行結果（architectは実装を
走らせない）。

### 1. 何が起きたか

ADR-0063決定3は、店を選び中の画面の集計と日程を4タブの奥へ移した。その決定が名指しで束ねたのは
`shopSelectionEntry`/`shortlistedShopVotes.list`・`candidateDateList`・`responseTable`・
`participantLinkList`の4つで、`participantLinkCopy`はその一覧に入っていなかった。契約は
`participantLinkCopy.presenceRule`（「SCHEDULINGまたはSELECTING_SHOPの間は存在」）を変えなかった
ため、実装は「タブの状態に関わらず出す」と読み、`gathering.js`の`renderShopSelectTabContent`が
全タブへ置いた（コード中の根拠コメントは「tester finding, TDR-GTH-36」）。後続の板との突き
合わせ（人間の2026-09-22フィードバック、ADR-0066）で、板S4の店タブの見出し行が「票が多い順｜店を
絞りなおす」の2点だけであり、実装は3点（右端に「リンクを発行」が加わる）になっていることが
見つかった。リンクは板では「リンク N本」タブに寄せてある。人間は2026-10-04に、契約を板に合わせる
選択肢Bを裁定した。

### 2. 「TDR-GTH-36」の指し先についての事実

実装コメントとL5テストのdocstringは、全タブでの存在の根拠を「TDR-GTH-36（どのタブでも到達
できる）」と書いている。しかし`.feature`のTDR-GTH-36は「確定後も幹事は既存のリンクを再コピー
できる」というFINALIZED局面の再コピーのシナリオで、タブにも発行にも触れていない。タブ越しの到達性
という要求は、tester が L4 の下準備（TDR-GTH-36のテストが、SELECTING_SHOPの会で既定の店タブから
UIで1本発行する）を通すために出した所見であり、契約にも`.feature`の本文にも書かれていない。本ADRは
その所見を、契約の要求としては採らない（検討した代替案を参照）。

## 決定

### 決定1. SELECTING_SHOP局面では、`participantLinkCopy`は「リンク」タブの中でだけ見える

`participantLinkCopy.presenceRule`へ次を足す（既存の文は消さず、この条件で狭める）。

- phaseがSELECTING_SHOPの間、この要素は`shopSelectionPanel.linksTab`が選ばれている
  （`aria-selected="true"`）ときだけ存在し、かつ見える。`shopTab`・`scheduleTab`・`answersTab`の
  どれかが選ばれている間は、**見えない**（DOMから取り除くか、隠すかは契約が固定しない）。店が1件でも
  入っているか（店タブの中身が一覧か「開いている店から選ぶ」のみか）にも依らない。
- phaseがSCHEDULINGの間は、タブ群（`shopSelectionPanel`）が存在せず、この要素は従来どおり
  ダッシュボードに直に存在し、見える（**変えない**）。
- phaseがFINALIZEDの間は従来どおり不在（**変えない**。`participantLinkList.issuanceClosed`の
  「発行はおわり」の札もそのまま）。

`shopSelectionPanel.linksTab.requiredOutcome`へ、「これを押すと`participantLinkList`が見え
るようになるのに加えて、`participantLinkCopy`も見えるようになる。他の3タブを押すと
`participantLinkCopy`は見えなくなる」を足す。`participantLinkList`自体の`presenceRule`
（3局面とも無条件）・`issueDialog`の`presenceRule`（押すまで不在）・`requiredOutcome`・
`data-issued-link-url`の置き場所・ADR-0058/0061が定めた2段の流れは**一切変えない**。発行ボタン
は新しい`testId`・`purpose`を持たない（既存の`gathering-participant-link-copy`のまま、
`allowedPurposes`は無変更）。

人間にとっての意味: 幹事は、店を選び中に新しいリンクを出したくなったら、まず「リンク N本」
タブを開き、そこで「リンクを発行」を押す。店タブ・日程タブ・回答タブにはもう出ない。

### 決定2. 契約バージョンは 0.25.0 → 0.26.0

`presenceRule`の意味が変わる改訂なので minor を刻む（ADR-0063が`phaseIndicatorAttributes`の
`presenceRule`を狭めたときに0.24.2→0.25.0としたのと同じ）。ヘッダに「2026-10-04 追補25」を
置く。具体的なYAML編集は契約の逐語FIND/REPLACEの形で別に提出する（architectにはこのファイルを
直接書き換える道具が無いため。ADR-0066の同梱`.spec`と同じ事情）。

### 決定3. 受け入れシナリオ（`.feature`）は足さず、変えない

置き場所（どのタブにあるか）は業務規則ではなくUIの構造であり、`.feature`は業務の言葉で書く
（`verification.md` L4）。ADR-0063が4タブの構造に対して`.feature`のシナリオを足さなかった
（足したのは見出しの内容のTDR-GTH-67だけ）のと同じ扱いとする。TDR-GTH-03（発行）・16〜20
（一覧・再コピー・失効）・35（確定後の発行拒否）・36（確定後の再コピー）の本文は、どれも
どのタブの話もしておらず、**書き換えない**。契約の`profiles.localAcceptance.verifiesScenarios`
も無変更。

## 検討した代替案

- **案A: 契約を変えず、店タブの見出し行にあるボタンだけを小さく（アイコンや小ボタンに）して板に
  寄せる。**却下（人間が選択肢Bを裁定した）。板の店タブの見出し行は2点だけで、小さくしても
  3点目が残る限り板どおりにはならない。日程・回答タブと店0件の画面に、板に無い専用の1行を
  足し続けることにもなる。得られたはずのもの: 全タブからの1回押しでの発行、契約・テストの無変更。
- **案C: 「どのタブでも到達できる」を契約の要求として明文化し、全タブで常に見えることを
  Mustにする。**却下。人間の板（店タブは2点のみ）と正面から衝突する。かつ、その要求の出どころ
  はtesterのL4下準備の都合であり、業務上の要求ではない（文脈2）。
- **案D: 「リンクを発行」を見出しの行ではなく、ダッシュボードの別の場所（≡のメニュー・地図の上
  のフローティングボタンなど）へ移す。**却下。板に根拠が無く、人間の裁定は「リンクは『リンク N本』
  タブに寄せる」である。
- **決定1で、`participantLinkCopy`をSELECTING_SHOPの間に限って完全に廃止する（このタブにも
  出さない）。**却下。店を選んでいる最中に参加者の抜けを補うため新しいリンクを出す運用は、
  TDR-GTH-35が拒否するのはFINALIZED後だけであること（SELECTING_SHOPでの発行は許される）からも
  業務上必要で、板が描かなかったのは「リンク」タブの中身そのものであって、発行の不要を示した
  わけではない（未決事項1）。
- **決定1で、`participantLinkCopy`と同じ並びで`issueDialog`にもタブ連動の条件を足す。**不要と
  判断。`issueDialog`は押した結果として出る小窓で、押せるのは`linksTab`が選ばれているときだけ
  なので、`presenceRule`（押すまで不在）の変更は要らない。小窓を開いている間は背面のタブを押せない
  （既存のモーダル）ため、小窓の最中にタブが変わる状況は契約が考えなくてよい。

## 影響を受けるもの

### 契約

- `contracts/gathering-scheduling-browser-interface.yaml`: ヘッダ追補25、`contractVersion`
  0.26.0、`participantLinkCopy.presenceRule`（SELECTING_SHOPの条件を追加）、
  `shopSelectionPanel.linksTab.requiredOutcome`（発行ボタンも見えるようになる、を追加）。
- `contracts/gathering-scheduling.feature`・`contracts/gathering-scheduling-api.yaml`・
  `contracts/test-support-api.yaml`: **無変更**。

### 受け入れシナリオ（L4。`tests/acceptance`）

シナリオ本文はどれも変わらない。ただし**下準備のコード**が影響を受ける。
- **TDR-GTH-36**（`test_gathering_scheduling_acceptance.py`、`test_tdr_gth_36_...`、1181行付近）:
  `organizer_has_a_selecting_shop_gathering`のあと、既定の店タブのままUIで
  `organizer_issues_a_participant_link()`を呼んでいる。契約変更後は「リンク」タブを開かないと
  ボタンが見えないので失敗する。直し方の候補は、(a) DSLの発行ヘルパーが先に
  `ensure_selecting_shop_links_tab_is_open()`を呼ぶ、(b) このテストだけ
  `a_participant_link_is_issued()`（API経由）で発行する。どちらでも本文は変わらない。
- `dsl/gathering_scheduling_browser.py`の`issue_participant_link_from_dashboard`（2177行）・
  `issue_participant_link_and_copy_via_dialog`（2210行）・`issue_n_participant_links_from_dashboard`
  （2238行）: 現在はタブを開かずにボタンを探す。SELECTING_SHOPの会で呼ぶ経路が出るなら、
  上の(a)のとおり`ensure_selecting_shop_links_tab_is_open()`（4173行、局面外では何もしない）を
  先に呼ぶ。SCHEDULING局面で呼ぶTDR-GTH-03・16〜20は影響なし。
- `assert_finalized_controls_are_absent`系（3161行、`PARTICIPANT_LINK_COPY`をFINALIZEDで不在と
  検査する）は、FINALIZEDの不在であり**影響なし**。

### UI不変量テスト（L5。`tests/ui_invariants`）

- **`test_render_invariants.py`の
  `test_gathering_dashboard_participant_link_copy_is_unconditional_on_shop_select_tab`
  （3470〜3512行）は、この決定が反転させる検査そのもの**で、書き換えが要る。「全タブで見える」
  を「`linksTab`選択中だけ見える。店・日程・回答では見えない（店0件と店1件以上の両方の
  分岐で）。SCHEDULING局面では直に見える」へ置き換える。クラスdocstringにある
  「TDR-GTH-36」への言及（3479行）も指し先を直す。
- 同ファイルで`linksTab`を先に開いてから発行ボタンを押している箇所（2894〜2911行のコア操作の
  キーボード検査、3190〜3200・3244行付近、4005〜4030行付近）は、決定1とそのまま整合する
  （無変更でよい）。SCHEDULING局面で押す箇所（2940〜2957行のキーボード検査、2967〜2976行の44px
  検査、3349行、`_build_participant_link`経由の3305・3750・3927行）も無変更。
- 44pxの宣言済みコントロールの掃引（`_assert_all_declared_gathering_controls_meet_44px`、
  3727・3788行付近のタブごとの掃引）は、タブごとに測定対象が変わるため、**各フェーズで測定件数が
  非ゼロであること**（activeContext「L5の44px検査で踏んだCI固有の罠」）が壊れていないかを
  実装後に確かめる必要がある。
- `test_layout_sanity.py`: `_issue_participant_link_url`（1303行）はSCHEDULING局面の呼び出し
  （1676行）なので無変更。1577〜1578行は`linksTab`を開いてから押しており整合。店タブの見出し行の
  幾何（8種の検査の対象になっている画面のうち、店タブの見出しに3点目が並んでいた状態）は、
  実装後にxfailの理由文・撮影の突き合わせで再確認する。
- `test_zz_capture_states.py`: `_issue_participant_link_url`（371行）は既に`linksTab`が
  あれば先に開く作りで整合。`tab_*`の撮影状態（722行）は、日程・回答タブに専用の1行が無く
  なった姿を撮り直す。

### 単体テスト（`tests/test_gathering.py`）

影響なし。ここの`issue_link`（1635行）・`issue_token`（3293行）はAPIのサーバ側の発行を呼ぶ
もので、画面のタブを扱わない。

### 実装（developerの領分。参考）

`gathering.js`の`renderShopSelectTabContent`（`linkCopyRow`を作る行と、`schedule`/`answers`/店0件
の3分岐が置く専用の1行、店タブの`gth-inline-actions`の中の`linkCopyButton`）と
`renderShopSelectionPanel`の`linkCopyButton`の組み立てが、決定1が取り除く対象。`links`分岐の
見出し行にある`linkCopyButton`は残る。`organizer.css`の`.gth-shop-panel-link-copy`
（1823〜1845行付近）と、771行付近のコメントも不要になる。architectは実装を書かない。

## 次工程への申し送り

1. 契約のYAML編集（逐語FIND/REPLACE）を適用し、`contractVersion`が0.26.0になっていることを
   govlint・契約スキーマlintで確かめる。
2. tester: 上記の L5 の書き換えと L4 下準備の修正（`.feature`は無変更）。
3. developer: `gathering.js`/`organizer.css`の取り除き。
4. orchestrator: ADR-0066決定4により、UIの束のPRの前に撮影と板との突き合わせ（店タブの見出し行が
   2点だけ・「リンク」タブの中身の見え方）を行う。

## 未決事項

1. **「リンク」タブの中身の置き場所（人間に確認）。**板S4は「リンク N本」タブの中身を描いて
   いない。決定1は、`gathering.js`の`links`分岐が既にそうしている「見出し行『発行済みリンク』の
   右に『リンクを発行』」という形を前提にしており、板の裏づけは無い。別の置き場所（一覧の下、
   フローティングなど）がよければ、承認のときに指示してほしい。契約はこの置き場所を固定しない
   ため、変えても契約は動かないが、tester・orchestratorの突き合わせの基準になる。板が無い状態は
   `board_compare.py`で赤く印される。designerに「リンク」タブの中身の板を描いてもらう選択も
   ある。
2. **タブを開く手間が増えること。**店タブからの発行は「タブを開く→押す」の2手になる。業務上の
   頻度は低い（参加者への配布は日程調整のSCHEDULING局面でほぼ済む）と見ているが、実機での使い
   勝手は未確認。
