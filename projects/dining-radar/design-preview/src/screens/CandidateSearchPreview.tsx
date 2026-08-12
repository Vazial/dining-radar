import { useMemo, useState } from "react";
import {
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  Info,
  MapPin,
  Menu,
  RefreshCw,
  SlidersHorizontal,
} from "lucide-react";

type ReviewState = "success" | "loading" | "empty" | "error" | "rate-limit";

type Candidate = {
  candidateRef: string;
  name: string;
  genre: string;
  regularHoliday: string;
  capacity: "少なめ" | "標準" | "多め";
  nonSmoking: "全席禁煙" | "一部禁煙" | "情報なし";
  dinnerBudget: "低" | "中" | "高";
  cardPaymentAvailable: boolean | null;
  providerPageUrl: string;
  visualPosition: { x: number; y: number };
};

const CANDIDATES: Candidate[] = [
  {
    candidateRef: "candidate-a",
    name: "架空食堂 青い匙",
    genre: "和食",
    regularHoliday: "日曜・祝日",
    capacity: "標準",
    nonSmoking: "全席禁煙",
    dinnerBudget: "中",
    cardPaymentAvailable: true,
    providerPageUrl: "https://example.invalid/shop-a",
    visualPosition: { x: 29, y: 42 },
  },
  {
    candidateRef: "candidate-b",
    name: "架空ビストロ 木曜日",
    genre: "洋食",
    regularHoliday: "月曜",
    capacity: "少なめ",
    nonSmoking: "一部禁煙",
    dinnerBudget: "高",
    cardPaymentAvailable: false,
    providerPageUrl: "https://example.invalid/shop-b",
    visualPosition: { x: 64, y: 27 },
  },
  {
    candidateRef: "candidate-c",
    name: "架空飯店 花鳥",
    genre: "中華",
    regularHoliday: "水曜",
    capacity: "多め",
    nonSmoking: "情報なし",
    dinnerBudget: "中",
    cardPaymentAvailable: null,
    providerPageUrl: "https://example.invalid/shop-c",
    visualPosition: { x: 72, y: 58 },
  },
  {
    candidateRef: "candidate-d",
    name: "架空喫茶 北窓",
    genre: "カフェ",
    regularHoliday: "不定休",
    capacity: "少なめ",
    nonSmoking: "全席禁煙",
    dinnerBudget: "低",
    cardPaymentAvailable: true,
    providerPageUrl: "https://example.invalid/shop-d",
    visualPosition: { x: 38, y: 69 },
  },
  {
    candidateRef: "candidate-e",
    name: "架空焼肉 灯台",
    genre: "焼肉",
    regularHoliday: "火曜",
    capacity: "標準",
    nonSmoking: "一部禁煙",
    dinnerBudget: "高",
    cardPaymentAvailable: false,
    providerPageUrl: "https://example.invalid/shop-e",
    visualPosition: { x: 53, y: 46 },
  },
];

const REVIEW_STATES: Array<{ value: ReviewState; label: string }> = [
  { value: "success", label: "通常" },
  { value: "loading", label: "読込中" },
  { value: "empty", label: "候補なし" },
  { value: "error", label: "取得失敗" },
  { value: "rate-limit", label: "回数制限" },
];

function StatusPanel({ state }: { state: Exclude<ReviewState, "success"> }) {
  const copy = {
    loading: ["候補を探しています", "ランチ営業の候補を確認しています。"],
    empty: ["条件に合う候補がありません", "絞り込み条件を変えてお試しください。"],
    error: ["候補情報を取得できませんでした", "時間をおいて、もう一度お試しください。"],
    "rate-limit": ["少し間をあけてください", "しばらく待つと、もう一度探せます。"],
  }[state];

  return (
    <section className={"preview-status preview-status--" + state}>
      {state === "loading" ? (
        <RefreshCw className="preview-status__spinner" aria-hidden="true" />
      ) : (
        <AlertTriangle aria-hidden="true" />
      )}
      <h2>{copy[0]}</h2>
      <p>{copy[1]}</p>
    </section>
  );
}

export default function CandidateSearchPreview() {
  const [reviewState, setReviewState] = useState<ReviewState>("success");
  const [reviewOpen, setReviewOpen] = useState(false);
  const [filterOpen, setFilterOpen] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [selectedRef, setSelectedRef] = useState(CANDIDATES[0].candidateRef);

  const selectedIndex = useMemo(
    () => Math.max(0, CANDIDATES.findIndex((candidate) => candidate.candidateRef === selectedRef)),
    [selectedRef],
  );

  const selectCandidate = (candidateRef: string) => {
    setSelectedRef(candidateRef);
    document
      .querySelector<HTMLElement>("[data-candidate-ref='" + candidateRef + "']")
      ?.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "center" });
  };

  const toggleDirty = () => setDirty((current) => !current);

  return (
    <div className="preview-app">
      <header className="preview-header">
        <div className="preview-title">
          <strong>ランチ候補</strong>
          <button className="icon-button icon-button--quiet" aria-label="この画面について">
            <Info size={17} />
          </button>
        </div>
        <button className="icon-button preview-account" aria-label="アカウントメニュー">
          <Menu size={20} />
        </button>
      </header>

      <main className="preview-main">
        {reviewState === "success" ? (
          <>
            <section className={"filter-surface " + (filterOpen ? "filter-surface--open" : "")}>
              <div className="filter-toolbar">
                <button
                  className="filter-summary"
                  type="button"
                  aria-expanded={filterOpen}
                  onClick={() => setFilterOpen((current) => !current)}
                >
                  <SlidersHorizontal size={17} aria-hidden="true" />
                  <span><small>条件</small> 居酒屋・バーを除く</span>
                  {dirty && <i aria-label="変更あり" />}
                  {filterOpen ? <ChevronUp size={17} /> : <ChevronDown size={17} />}
                </button>
                <button className="icon-button filter-refresh" type="button" aria-label="もう一度探す">
                  <RefreshCw size={18} />
                </button>
              </div>

              {filterOpen && (
                <div className="filter-panel">
                  <div className="filter-row">
                    <span className="filter-row__label">ジャンル</span>
                    <div className="filter-rail" aria-label="ジャンル">
                      {["和食", "洋食", "中華", "ラーメン", "ほか5件…"].map((label) => (
                        <button type="button" className="filter-chip" onClick={toggleDirty} key={label}>{label}</button>
                      ))}
                    </div>
                  </div>
                  <div className="filter-row">
                    <span className="filter-row__label">こだわり</span>
                    <div className="filter-rail" aria-label="こだわり">
                      <button type="button" className="filter-chip" onClick={toggleDirty}>禁煙席あり</button>
                      <button type="button" className="filter-chip" onClick={toggleDirty}>カード利用不可を除く</button>
                      <button type="button" className="filter-chip" onClick={toggleDirty}>居酒屋等も含む</button>
                    </div>
                  </div>
                  <div className="filter-row">
                    <span className="filter-row__label">夜予算</span>
                    <div className="filter-rail" aria-label="ディナー予算感">
                      {["低", "中", "高"].map((label) => (
                        <button type="button" className="filter-chip filter-chip--square" onClick={toggleDirty} key={label}>{label}</button>
                      ))}
                    </div>
                  </div>
                  <div className="filter-panel__footer">
                    <p>ディナー予算をもとにした目安です。</p>
                    {dirty && <button className="filter-apply" type="button" onClick={() => setDirty(false)}>5件を表示</button>}
                  </div>
                </div>
              )}
            </section>

            <section className="decision-surface" aria-label="候補と地図">
              <div className="synthetic-map" aria-label="合成地図">
                <div className="map-grid" />
                <div className="map-road map-road--one" />
                <div className="map-road map-road--two" />
                <div className="map-park" />
                {CANDIDATES.map((candidate, index) => (
                  <button
                    key={candidate.candidateRef}
                    type="button"
                    className={"map-marker " + (selectedRef === candidate.candidateRef ? "map-marker--selected" : "")}
                    style={{ left: candidate.visualPosition.x + "%", top: candidate.visualPosition.y + "%" }}
                    aria-label={candidate.name}
                    onClick={() => selectCandidate(candidate.candidateRef)}
                  >
                    {index + 1}
                  </button>
                ))}
                <a className="map-attribution" href="https://www.openstreetmap.org/copyright" onClick={(event) => event.preventDefault()}>
                  © OpenStreetMap contributors
                </a>
              </div>

              <div className="deck-counter" aria-live="polite">
                <MapPin size={14} /> {selectedIndex + 1} / {CANDIDATES.length}
              </div>

              <div className="candidate-deck">
                {CANDIDATES.map((candidate, index) => (
                  <article
                    key={candidate.candidateRef}
                    data-candidate-ref={candidate.candidateRef}
                    className={"compact-card " + (selectedRef === candidate.candidateRef ? "compact-card--selected" : "")}
                    tabIndex={0}
                    onClick={() => setSelectedRef(candidate.candidateRef)}
                  >
                    <div className="compact-card__identity">
                      <span className="candidate-number">{index + 1}</span>
                      <span className="candidate-genre">{candidate.genre}</span>
                    </div>
                    <h2>{candidate.name}</h2>
                    <div className="fact-strip" aria-label="店舗の参考情報">
                      <span>席数 {candidate.capacity}</span>
                      <span>{candidate.nonSmoking}</span>
                      <span>夜予算 {candidate.dinnerBudget}</span>
                    </div>
                    <div className="compact-card__footer">
                      <div>
                        <small>定休日</small>
                        <strong>{candidate.regularHoliday}</strong>
                      </div>
                      <a
                        href={candidate.providerPageUrl}
                        onClick={(event) => { event.preventDefault(); event.stopPropagation(); }}
                      >
                        店舗情報 <ExternalLink size={15} />
                      </a>
                    </div>
                    {candidate.cardPaymentAvailable === false && (
                      <p className="payment-caution">クレジットカードは利用できません</p>
                    )}
                  </article>
                ))}
              </div>

              <a
                className="provider-credit"
                href="http://webservice.recruit.co.jp/"
                onClick={(event) => event.preventDefault()}
              >
                Powered by ホットペッパーグルメ Webサービス
              </a>
            </section>
          </>
        ) : (
          <StatusPanel state={reviewState} />
        )}
      </main>

      <aside className={"review-console " + (reviewOpen ? "review-console--open" : "")}>
        {reviewOpen && (
          <div className="review-console__states">
            <strong>レビュー状態</strong>
            {REVIEW_STATES.map((state) => (
              <button
                type="button"
                className={reviewState === state.value ? "active" : ""}
                onClick={() => setReviewState(state.value)}
                key={state.value}
              >
                {state.label}
              </button>
            ))}
          </div>
        )}
        <button className="review-console__toggle" type="button" onClick={() => setReviewOpen((current) => !current)}>
          {reviewOpen ? "閉じる" : "状態確認"}
        </button>
      </aside>
    </div>
  );
}
