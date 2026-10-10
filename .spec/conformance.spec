# ADR-0075 同梱: 契約YAMLの逐語FIND/REPLACE（KEN-53）
#
# architect には contracts/ 配下を直接書き換える道具が無い（Read/Grep/Glob/Write のみ。ADR-0066・0068 と同じ事情）。
# 適用は orchestrator（または developer）が行う。記法は ADR-0066 の同梱 .spec と同じ最善の推測:
#   「## OP n: <相対パス>」の見出し、FIND/REPLACE は <<< と >>> で囲む。FIND は実ファイルからの逐語コピー。
#   apply_spec.py の実際の記法と違う場合は区切りだけ直して適用すること（本文は変えない）。
# 適用後の確認: contractVersion が candidate 1.16.0 / gathering 0.31.0 になっていること、YAML として読めること、
#   govlint・契約スキーマ lint が通ること。FIND が1回だけ一致することを各OPで確かめること。

## OP 1: projects/dining-radar/contracts/candidate-search-browser-interface.yaml
FIND:
<<<
# - 本追補はYAMLの下書きである（architect起草、人間の承認後に確定する。ADR-0069の`approved_by`参照）。

contractVersion: '1.15.0'
>>>
REPLACE:
<<<
# - 本追補はYAMLの下書きである（architect起草、人間の承認後に確定する。ADR-0069の`approved_by`参照）。

# 2026-10-09 追補 (architect、ADR-0075【承認済み】。KEN-53、監査
# audit-board-vs-implementation-2026-10-08.md の B-2。人間裁定「板どおり。PCでは≡と見出し(h1)を
# 同じ行に置く（画面名が左、≡が右）」への対応。ADR-0066決定3の「画面上端の行（この画面自身の見出しを
# 載せる行）」が、≡だけの行と見出しの行が別でも満たされてしまっていた読みの隙間を、機械が測れる形で
# 閉じる。contractVersionを1.15.0から1.16.0へ上げる):
# - **`gatheringEntry.primaryNavigationGeometry.topBar`を新設する**（ADR-0075決定1）: twoColumnLayoutで
#   menuToggleが出る全画面（候補画面[通常・会モード]・会の一覧・会をつくる・幹事画面の3局面）の最上段を
#   「左に画面名・右にmenuToggle」の1本のバー行にする。判定は幾何条件TB-1〜TB-4（同じ行／画面名が左／
#   バー行の上に何も無い／レベル1見出しが画面に1つ）。画面名の要素は、候補画面・会の一覧・会をつくる
#   ではその画面のh1、幹事画面では新設の`gathering-dashboard-top-label`（幹事画面のh1は会の名前のまま、
#   バー行の下。gathering-scheduling-browser-interface.yaml 側に定義）。
# - 既存のtwoColumnLayout節（menuToggleは行の右端・menuDotはmenuToggleの右上・menuPanelは下に右端を
#   揃えて開く）は無変更。mapPrimaryTouchLayout（スマホ）は無変更（≡が無いので対象外）。
# - `candidate-search.feature`は無変更（ADR-0075決定4。位置と並びはUIの構造で業務規則ではない）。
# - 具体的なYAML編集は本ADRに同梱する`.spec/conformance.spec`が持つ。architect自身は`contracts/`配下の
#   YAMLへ直接書き込まない。

contractVersion: '1.16.0'
>>>

## OP 2: projects/dining-radar/contracts/candidate-search-browser-interface.yaml
FIND:
<<<
      instead of its top-right, and opened a panel that ran off the
      viewport's left edge.
    mapPrimaryTouchLayout: >-
>>>
REPLACE:
<<<
      instead of its top-right, and opened a panel that ran off the
      viewport's left edge.
    topBar:
      addedBy: ADR-0075 decision 1
      appliesWhen: twoColumnLayout holds and menuToggle is present
      requirement: >-
        Added 2026-10-09 (ADR-0075 decision 1; human ruling B-2 "板どおり",
        KEN-53; boards party2/f1 N1-b, party2/b2 Q1-a and Q5-a, party2/d4r
        G1/G2, party2/d7 S4 all draw the same top bar: the screen's name at
        the left and the menu control at the right, one line). Whenever
        twoColumnLayout holds, on every screen that carries menuToggle --
        the authenticated candidate-search screen (ordinary and
        gatheringMode), organizerGatheringList, organizerGatheringCreate,
        and organizerDashboard in each of its three phases -- the top of the
        page is ONE bar row: the screen's name (barLabel below) at the left
        and menuToggle at the right, on the same line. No row of its own
        that holds menuToggle alone may sit above the row holding the
        screen's name. This closes a reading gap in the clause above (and
        in ADR-0066 decision 3): "the row carrying this screen's own
        heading" did not say that the heading and menuToggle share a line,
        and a build that put menuToggle alone on its own first row, with the
        heading on the row below, satisfied the words while contradicting
        the board (2026-10-08 audit, B-2). Position and adjacency are Musts
        (ADR-0066 decision 2); the bar's height, padding, font size, and
        color remain unfixed visual choices. This clause does not apply
        under mapPrimaryTouchLayout (menuToggle does not exist there) and
        does not apply to screens that never carry menuToggle (login,
        password change).
      barLabel:
        candidateSearch: the screen's single level-1 heading (h1)
        organizerGatheringList: the screen's single level-1 heading (h1)
        organizerGatheringCreate: the screen's single level-1 heading (h1)
        organizerDashboard: >-
          gathering-dashboard-top-label (gathering-scheduling-browser-
          interface.yaml, organizerDashboard.topBarLabel) -- NOT the h1.
          On this screen the h1 is the gathering's own name
          (organizerDashboard.headingBar.title), which the board draws on a
          row below the bar and below the return link (ADR-0069 decision 3
          item 5 already reads the bar, not the name row, as "the top row").
      geometry:
        note: >-
          S = the barLabel element of the screen under test; T = menuToggle.
          Boxes are the elements' rendered border boxes in CSS pixels.
          Tolerances are 1px unless stated. All four conditions are
          assessed with twoColumnLayout holding (the L5 harness's 1440x900
          viewport satisfies it; a viewport narrower than twoColumnLayout's
          threshold is out of scope for this clause).
        TB-1-sameRow: >-
          S and T overlap vertically (S.top < T.bottom and T.top < S.bottom)
          and S's vertical center lies within T's vertical extent
          [T.top, T.bottom]. In words: the screen's name and the menu
          control are on the same line.
        TB-2-nameAtLeft: >-
          S lies wholly to the left of T (S.right <= T.left). In words: the
          name is at the left, the menu control at the right (T's own
          right-end position is the clause above, unchanged).
        TB-3-nothingAboveTheBar: >-
          No visible element that carries its own text or is operable has
          its bottom edge at or above min(S.top, T.top). In words: nothing
          sits wholly above the bar row -- in particular no row holding
          menuToggle alone. (Page background and containers that merely
          enclose S and T are not "above" it.)
        TB-4-singleLevelOneHeading: >-
          The screen renders exactly one level-1 heading (h1). On
          candidateSearch, organizerGatheringList and
          organizerGatheringCreate that h1 is S itself. On organizerDashboard
          it is gathering-dashboard-title in every phase (see
          gathering-scheduling-browser-interface.yaml,
          organizerDashboard.headingBar.title), and S
          (gathering-dashboard-top-label) is not a heading of level 1.
      verificationAllocation:
        L5: >-
          tests/ui_invariants extends test_layout_sanity.py's
          test_primary_navigation_geometry (ADR-0066 decision 3's
          standalone-assertion gap) to assert TB-1 to TB-4 at 1440x900 for:
          the candidate-search screen (ordinary, and gatheringMode),
          organizerGatheringList, organizerGatheringCreate, and
          organizerDashboard in SCHEDULING, SELECTING_SHOP and FINALIZED.
          Locators: menuToggle by testId candidate-primary-nav-menu-toggle;
          S by the h1 element for the first three screens, by testId
          gathering-dashboard-top-label for organizerDashboard. This is a
          developer-maintained assertion for a Must this decision already
          fixes (adr/0020 decision 6 lane; no new ADR needed).
    mapPrimaryTouchLayout: >-
>>>

## OP 3: projects/dining-radar/contracts/gathering-scheduling-browser-interface.yaml
FIND:
<<<
#   `.feature`は無変更。押せる部品は増えず、業務規則も増えない。
#
openapi_note: >-
>>>
REPLACE:
<<<
#   `.feature`は無変更。押せる部品は増えず、業務規則も増えない。
#
# 2026-10-09 追補 (architect、ADR-0075【承認済み】。KEN-53、監査 audit-board-vs-implementation-2026-10-08.md の
#   B-2・B-3。人間裁定「B-2: 板どおり、PCでは≡と見出しを同じ行に置く。B-3: 店選び中・日程を聞いている
#   幹事画面にも『‹ ランチ会』の戻り道を足す（確定後と同じ形）」。板 party2/d7 S4（店選び中）・
#   party2/b2 Q5-a（日程を聞き中）。contractVersionを0.30.0から0.31.0へ上げる):
# - **`organizerDashboard.headingBar`をSCHEDULING局面にも広げた**（ADR-0075決定2）: これまでSELECTING_SHOPと
#   FINALIZEDで出現していたが、SCHEDULING・SELECTING_SHOP・FINALIZEDの3局面すべてで出現する。ただし
#   `confirmedDate`はSELECTING_SHOPだけ（無変更）。SCHEDULINGの「会の名前」はこれまでtestIdを持たない
#   要素だったが、`title`（gathering-dashboard-title）になる。
# - **`headingBar.backLink`（gathering-dashboard-back）を3局面に広げた**（ADR-0075決定2）: FINALIZEDだけ
#   だったのを、SCHEDULING・SELECTING_SHOP・FINALIZEDの3局面で出現させる。形は確定後と同じ（会の一覧への
#   平叙な`<a href>`、会の名前の上）。位置を幾何条件BL-1〜BL-3としてMustにした。
# - **`headingBar.title`は3局面すべてで画面唯一のh1になった**（ADR-0075決定2）: これまでFINALIZEDだけが
#   h1で、SCHEDULING・SELECTING_SHOPのダッシュボードにはh1が無かった（ADR-0069が汎用見出し「会の日程調整」を
#   外したため）。
# - **`organizerDashboard.topBarLabel`を新設した**（ADR-0075決定1、testId`gathering-dashboard-top-label`）:
#   twoColumnLayoutで、ダッシュボードの最上段のバー行の左に出る画面名（板の「ランチ会」）。h1ではない。
#   バー行の幾何条件（同じ行・左・上に何も無い）は candidate-search-browser-interface.yaml の
#   `primaryNavigationGeometry.topBar`（TB-1〜TB-4）が規範源。
# - `profiles.localAcceptance.verifiesScenarios`・`allowedPurposes`・`formControlExemptTestIds`・
#   `.feature`は無変更（押せる部品は増えず、topBarLabelは表示専用の`<span>`、業務規則も増えない）。
#
openapi_note: >-
>>>

## OP 4: projects/dining-radar/contracts/gathering-scheduling-browser-interface.yaml
FIND:
<<<
contractVersion: '0.30.0'
>>>
REPLACE:
<<<
contractVersion: '0.31.0'
>>>

## OP 5: projects/dining-radar/contracts/gathering-scheduling-browser-interface.yaml
FIND:
<<<
    auth-password-change-open from any of these three screens -- previously
    reachable only from the candidate-search screen.

browserControlSurface:
>>>
REPLACE:
<<<
    auth-password-change-open from any of these three screens -- previously
    reachable only from the candidate-search screen.
  crossFileSharedNavigationNoteAdr0075: >-
    Added 2026-10-09 (ADR-0075 decision 1). Under twoColumnLayout the
    position of menuToggle on these three screens is now also governed by
    candidate-search-browser-interface.yaml's gatheringEntry.
    primaryNavigationGeometry.topBar (TB-1 to TB-4): the screen's name and
    menuToggle share one bar row, name at the left, nothing above it. This
    file adds no test id for organizerGatheringList or
    organizerGatheringCreate (their screen name is the h1 itself); for
    organizerDashboard it defines topBarLabel
    (gathering-dashboard-top-label) below. The normative source of the
    geometry stays on the candidate-search side, as ADR-0059 decision 6
    established for the shared navigation.

browserControlSurface:
>>>

## OP 6: projects/dining-radar/contracts/gathering-scheduling-browser-interface.yaml
FIND:
<<<
    headingBar:
      description: >-
        Added 2026-09-19 (architect, ADR-0063 decision 2, board
>>>
REPLACE:
<<<
    topBarLabel:
      testId: gathering-dashboard-top-label
      formControl: false
      presenceRule: >-
        Added 2026-10-09 (ADR-0075 decision 1; human ruling B-2, boards
        party2/d4r G1/G2, party2/d7 S4, party2/b2 Q5-a: the bar's left side
        reads 「ランチ会」). Present, in all three phases (SCHEDULING,
        SELECTING_SHOP, FINALIZED), exactly while twoColumnLayout holds
        (candidate-search-browser-interface.yaml renderModes). Under
        mapPrimaryTouchLayout this contract neither requires nor forbids
        it (the board's phone bar also reads 「ランチ会」 but the bottom
        navigation, not a bar row, is the phone's navigation).
      requirement: >-
        A display-only, non-interactive element (a `<span>`/`<div>`, not a
        link, not a heading of level 1; outside forbiddenFormControlCategories'
        scan and not in formControlExemptTestIds because it is not a form
        control or anchor). It is the screen's name in the top bar row:
        candidate-search-browser-interface.yaml's primaryNavigationGeometry.
        topBar fixes where it sits relative to menuToggle (TB-1 same line,
        TB-2 at the left, TB-3 nothing above). Its visible wording is not
        fixed by this contract (the board draws 「ランチ会」) but it carries
        non-empty visible text. It is deliberately not the screen's h1: the
        h1 is headingBar.title, the gathering's own name, drawn by the
        board on a row below this bar and below headingBar.backLink
        (ADR-0069 decision 3 item 5; ADR-0075 decision 1).
    headingBar:
      description: >-
        Added 2026-09-19 (architect, ADR-0063 decision 2, board
>>>

## OP 7: projects/dining-radar/contracts/gathering-scheduling-browser-interface.yaml
FIND:
<<<
        (see phaseIndicatorAttributes) alongside this heading. Absent
        while phase is SCHEDULING. Supports TDR-GTH-67.
>>>
REPLACE:
<<<
        (see phaseIndicatorAttributes) alongside this heading.
        **Widened again 2026-10-09 (ADR-0075 decision 2, human ruling
        B-3, boards party2/d7 S4 and party2/b2 Q5-a)**: headingBar is now
        also present while phase is SCHEDULING, so it is present in all
        three phases. What differs per phase: backLink and title are
        present in all three; confirmedDate is present in SELECTING_SHOP
        only (unchanged). In SCHEDULING the badge
        (phaseIndicatorAttributes), the statistics and the delete button
        stay where they are (not made Musts); the gathering's name, which
        had no test id in SCHEDULING before, is now title. Supports
        TDR-GTH-67.
>>>

## OP 8: projects/dining-radar/contracts/gathering-scheduling-browser-interface.yaml
FIND:
<<<
        presenceRule: >-
          Added 2026-10-04 (ADR-0069 decision 3, board party2/d4r
          G1/G2's "‹ ランチ会" return path). Present exactly while phase
          is FINALIZED. Absent for SELECTING_SHOP -- no board has ruled
          a return path for that phase's heading yet (ADR-0069 flags
          this as an open question rather than extending the ruling).
>>>
REPLACE:
<<<
        presenceRule: >-
          Added 2026-10-04 (ADR-0069 decision 3, board party2/d4r
          G1/G2's "‹ ランチ会" return path). **Widened 2026-10-09
          (ADR-0075 decision 2, human ruling B-3)**: present in all three
          phases -- SCHEDULING, SELECTING_SHOP and FINALIZED -- at every
          viewport width. (It was FINALIZED only; ADR-0069 left
          SELECTING_SHOP out because no board had ruled it. Board
          party2/d7 S4 now rules SELECTING_SHOP and board party2/b2 Q5-a
          rules SCHEDULING; both draw 「‹ ランチ会」 above the
          gathering's name.)
>>>

## OP 9: projects/dining-radar/contracts/gathering-scheduling-browser-interface.yaml
FIND:
<<<
          record. Its visible wording (the board draws "ランチ会" with a
          leading chevron) is not fixed by this contract.
>>>
REPLACE:
<<<
          record. Its visible wording (the board draws "ランチ会" with a
          leading chevron) is not fixed by this contract. **Position
          (ADR-0075 decision 2; a board-ruled position, so a Must per
          ADR-0066 decision 2)**, with T = menuToggle and L = this element
          and N = title, boxes as rendered border boxes in CSS pixels,
          tolerances 1px unless stated:
          BL-1 (above the name) L.bottom <= N.top and L's vertical center
          is above N's vertical center, in every phase and at every width;
          BL-2 (aligned with the name) |L.left - N.left| <= 4px;
          BL-3 (below the bar) while twoColumnLayout holds, L lies wholly
          below the bar row of candidate-search-browser-interface.yaml's
          primaryNavigationGeometry.topBar, i.e. L.top >= max(topBarLabel.
          bottom, T.bottom) - 1. In document order it comes immediately
          before title (unchanged from ADR-0069). It is an operable anchor
          and the ADR-0020 decision 4(e) 44px floor applies to it as to
          every operable element; no exemption is added.
>>>

## OP 10: projects/dining-radar/contracts/gathering-scheduling-browser-interface.yaml
FIND:
<<<
          FINALIZED, backLink above comes before this element in document
          order and is rendered directly above it (board G1/G2).
>>>
REPLACE:
<<<
          FINALIZED, backLink above comes before this element in document
          order and is rendered directly above it (board G1/G2).
          **Widened 2026-10-09 (ADR-0075 decision 2)**: this holds in
          every phase, not FINALIZED only -- in SCHEDULING and
          SELECTING_SHOP too this element is the one level-1 heading
          (`<h1>`) of the screen (until now neither phase's dashboard
          rendered any h1; in SELECTING_SHOP the element was a `<span>`,
          in SCHEDULING the name had no test id), the screen renders no
          other level-1 heading, and backLink is directly above it
          (backLink BL-1 to BL-3). In SCHEDULING this element carries
          data-gathering-title only; it does not carry the date
          (confirmedDate stays SELECTING_SHOP only).
>>>

## OP 11: projects/dining-radar/contracts/gathering-scheduling-browser-interface.yaml
FIND:
<<<
        followed by addCandidateDateOpen; (7) participantLinkList. The
        previous standalone "日程" heading is removed.
>>>
REPLACE:
<<<
        followed by addCandidateDateOpen; (7) participantLinkList. The
        previous standalone "日程" heading is removed. **Above (1)**
        (ADR-0075, 2026-10-09), in DOM and on screen, top to bottom: the
        top bar row (topBarLabel at the left, menuToggle at the right,
        twoColumnLayout only), then headingBar.backLink, then
        headingBar.title (the gathering's name, the screen's h1). The
        block numbered (1) here is the in-content block heading
        「日を決める」, not the screen's h1, and is unchanged.
>>>
